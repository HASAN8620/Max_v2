import os
import re
import json
import time
import requests
import sys

# ==========================================
# 1. GROQ API KEYS SETUP
# ==========================================
KEYS_ENV = os.environ.get("GROQ_API_KEYS", "")
API_KEYS = [k.strip() for k in KEYS_ENV.split(",") if k.strip()]

if not API_KEYS:
    print("❌ ERROR: GROQ_API_KEYS secret nahi mila.")
    sys.exit(1)

print(f"✅ SYSTEM: Total {len(API_KEYS)} Groq Keys Loaded! 🚀")

INPUT_FILE = "american.oxt"
OUTPUT_FILE = "american_roman.oxt"
CHECKPOINT_FILE = "translation_checkpoint.json"
BATCH_SIZE = 20

# ⚠️ llama-3.3-70b-versatile is being shut down by Groq on 08/16/26.
# Switched to their recommended replacement: openai/gpt-oss-120b
# (alternative: qwen/qwen3.6-27b). See https://console.groq.com/docs/deprecations
MODEL_NAME = "openai/gpt-oss-120b"
curr_key_idx = 0

# ==========================================
# 2. SECURITY LAYER (PROMPT & AUTO-CORRECTOR)
# ==========================================
SYSTEM_PROMPT = """You are an elite video game localization expert from Pakistan.
Your task is to translate Max Payne 3 English dialogues into NATURAL, DRAMATIC, and GRITTY Pakistani Roman Urdu (WhatsApp style).

STRICT OUTPUT RULES:
1. You MUST respond with ONLY a valid JSON object matching the exact input keys. Do not add explanations.
2. The tone must be mature, cynical, and native to a Pakistani speaker.

STRICTLY FORBIDDEN HINDI WORDS (MUST USE URDU):
- NEVER use 'shareer' -> use 'jism'
- NEVER use 'samay' -> use 'waqt'
- NEVER use 'dard nivaarak' -> use 'painkillers'
- NEVER use 'swasthya' -> use 'sehat'
- NEVER use 'karya' -> use 'kaam'
- NEVER use 'bhavnaon' -> use 'ehsaas' or 'jazbaat'
- NEVER use 'khojne' -> use 'dhoondne'
- NEVER use 'vishesh' -> use 'khaas'
- NEVER use 'vah' -> use 'woh'
- NEVER use 'ladaai' -> use 'larai'
- NEVER use 'badi' / 'bada' -> use 'bari' / 'bara'
- NEVER use 'prayas' -> use 'koshish'
- NEVER use 'kintu' / 'parantu' -> use 'lekin' / 'par'
- NEVER use 'shanti' -> use 'sakoon'

GAMING TERMS TO KEEP IN ENGLISH:
'painkillers', 'ammo', 'guns', 'checkpoint', 'comfort zone', 'health', 'plan B', 'cops'.

Keep ALL formatting tags (~z~, ~w~, ~n~, ~a~, ~g~, ~b~) EXACTLY in their original positions."""

HINDI_TO_URDU = {
    r'\bsamay\b': 'waqt', r'\bshareer\b': 'jism', r'\bdard nivaarak\b': 'painkillers',
    r'\bswasthya\b': 'sehat', r'\bkarya\b': 'kaam', r'\bbhavnaon\b': 'ehsaas',
    r'\bkhojne\b': 'dhoondne', r'\bvishesh\b': 'khaas', r'\bvah\b': 'woh',
    r'\bladaai li\b': 'larai hui', r'\bladaai\b': 'larai', r'\bbadi\b': 'bari',
    r'\bbada\b': 'bara', r'\bprayas\b': 'koshish', r'\bshanti\b': 'sakoon',
    r'\bpratiksha\b': 'intezar', r'\bavashya\b': 'zaroor', r'\bkintu\b': 'lekin',
    r'\bparantu\b': 'lekin'
}

def clean_hindi_words(text):
    if not isinstance(text, str):
        return text
    for pattern, replacement in HINDI_TO_URDU.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# ==========================================
# 3. BATCH TRANSLATION + API ROTATION (with REAL debug output)
# ==========================================
def translate_batch(batch_dict):
    """Returns a dict of translations on success, or None if every key/attempt failed.
    NO git/os.system calls here - this function only ever touches the API and local files."""
    global curr_key_idx
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = f"Translate to Roman Urdu. Return ONLY JSON:\n{json.dumps(batch_dict, ensure_ascii=False)}"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    max_attempts = len(API_KEYS) * 2

    for attempt in range(1, max_attempts + 1):
        key_num = curr_key_idx + 1
        headers = {"Authorization": f"Bearer {API_KEYS[curr_key_idx]}", "Content-Type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                try:
                    parsed = json.loads(content.strip())
                    if isinstance(parsed, dict) and parsed:
                        return {k: clean_hindi_words(v) for k, v in parsed.items()}
                    print(f"\n⚠️ Key #{key_num} (attempt {attempt}/{max_attempts}): 200 OK but JSON was empty/not an object. Raw: {content[:300]!r}", flush=True)
                except json.JSONDecodeError as je:
                    print(f"\n⚠️ Key #{key_num} (attempt {attempt}/{max_attempts}): 200 OK but NOT valid JSON ({je}). Raw: {content[:300]!r}", flush=True)
            else:
                # THE ACTUAL response body from Groq, so you can see the real reason (bad model, bad key, rate limit, etc.)
                print(f"\n⚠️ Key #{key_num} (attempt {attempt}/{max_attempts}) HTTP {response.status_code}: {response.text[:500]}", flush=True)

        except requests.exceptions.RequestException as e:
            print(f"\n⚠️ Key #{key_num} (attempt {attempt}/{max_attempts}) Connection error: {repr(e)}", flush=True)

        curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
        time.sleep(2)

    print("\n🚨 CRITICAL: Is batch ke liye saari keys/attempts fail ho gaye. Jo ho chuka hai woh save kar ke ruk rahe hain.", flush=True)
    return None

# ==========================================
# 4. CORE LOGIC & RESUME SYSTEM
# ==========================================
if not os.path.exists(INPUT_FILE):
    print(f"❌ ERROR: '{INPUT_FILE}' file nahi mili.")
    sys.exit(1)

print(f"📁 Reading source file: {INPUT_FILE}", flush=True)

saved_data = {}
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        try:
            saved_data = json.load(f)
            saved_data = {k: clean_hindi_words(v) for k, v in saved_data.items()}
            if saved_data:
                print(f"🔄 RESUME ACTIVE: {len(saved_data)} lines pehle se tayyar hain!", flush=True)
        except Exception:
            saved_data = {}

with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    all_lines = f.readlines()

pending_batch = {}
total_dialogues = sum(1 for line in all_lines if re.search(r'=\s*~(z|w)~', line))
print(f"🎯 Total Dialogues to Translate: {total_dialogues}")

def save_checkpoint():
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf:
        json.dump(saved_data, cf, ensure_ascii=False, indent=2)

stopped_early = False

for line in all_lines:
    if re.search(r'=\s*~(z|w)~', line):
        k = line.split('=', 1)[0].strip()

        if k not in saved_data:
            pending_batch[k] = line.split('=', 1)[1].strip()

        if len(pending_batch) >= BATCH_SIZE:
            current_progress = len(saved_data) + len(pending_batch)
            print(f"\n🚀 Translating ({MODEL_NAME})... ({current_progress}/{total_dialogues})", flush=True)

            res = translate_batch(pending_batch)
            if res:
                saved_data.update(res)
                save_checkpoint()  # Local save only - GitHub Actions workflow handles the push
            else:
                stopped_early = True
                break

            pending_batch = {}
            time.sleep(1.0)

if not stopped_early and pending_batch:
    res = translate_batch(pending_batch)
    if res:
        saved_data.update(res)
        save_checkpoint()
    else:
        stopped_early = True

# Always rebuild the output file with whatever we have, even on an early stop,
# so a single failed batch doesn't leave american_roman.oxt completely unwritten.
print("\n🔨 Rebuilding final american_roman.oxt file...", flush=True)
converted_count = 0

with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for line in all_lines:
        if re.search(r'=\s*~(z|w)~', line):
            k = line.split('=', 1)[0].strip()
            if k in saved_data:
                clean_text = clean_hindi_words(saved_data[k])
                out.write(f"{k} = {clean_text}\n")
                converted_count += 1
            else:
                out.write(line)
        else:
            out.write(line)

print(f"\n🎉 {converted_count}/{total_dialogues} lines Successfully Converted via Groq!", flush=True)

if stopped_early:
    print("⏸️ Is run mein saari keys fail hui, isliye poora batch nahi ho saka. Jo translate ho chuka hai woh checkpoint mein save hai - agli run isi se RESUME karegi.", flush=True)

sys.exit(0)  # Always exit 0 - the workflow's commit-and-push step reads files from disk, not the exit code
