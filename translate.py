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
    print("❌ ERROR: GROQ_API_KEYS secret nahi mila. GitHub Settings check karein.")
    sys.exit(1)

print(f"✅ SYSTEM: Total {len(API_KEYS)} Groq Keys Loaded! 🚀")

INPUT_FILE = "american.oxt"
OUTPUT_FILE = "american_roman.oxt"
CHECKPOINT_FILE = "translation_checkpoint.json"
BATCH_SIZE = 20
MODEL_NAME = "llama-3.3-70b-versatile"  # Groq ka sab se smart aur heavy model
curr_key_idx = 0

# ==========================================
# 2. SECURITY LAYER 1: STRICT AI PROMPT
# ==========================================
SYSTEM_PROMPT = """You are an elite video game localization expert from Pakistan.
Your task is to translate Max Payne 3 English dialogues into NATURAL, DRAMATIC, and GRITTY Pakistani Roman Urdu (WhatsApp style).

STRICT OUTPUT RULES:
1. You MUST respond with ONLY a valid JSON object. NO markdown, NO explanations.
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

# ==========================================
# 3. SECURITY LAYER 2: PYTHON AUTO-CORRECTOR (THE BOSS)
# ==========================================
HINDI_TO_URDU = {
    r'\bsamay\b': 'waqt',
    r'\bshareer\b': 'jism',
    r'\bdard nivaarak\b': 'painkillers',
    r'\bswasthya\b': 'sehat',
    r'\bkarya\b': 'kaam',
    r'\bbhavnaon\b': 'ehsaas',
    r'\bkhojne\b': 'dhoondne',
    r'\bvishesh\b': 'khaas',
    r'\bvah\b': 'woh',
    r'\bladaai li\b': 'larai hui',
    r'\bladaai\b': 'larai',
    r'\bbadi\b': 'bari',
    r'\bbada\b': 'bara',
    r'\bprayas\b': 'koshish',
    r'\bshanti\b': 'sakoon',
    r'\bpratiksha\b': 'intezar',
    r'\bavashya\b': 'zaroor',
    r'\bkintu\b': 'lekin',
    r'\bparantu\b': 'lekin'
}

def clean_hindi_words(text):
    if not isinstance(text, str):
        return text
    for pattern, replacement in HINDI_TO_URDU.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# ==========================================
# 4. GROQ FAST TRANSLATION BATCH
# ==========================================
def translate_batch(batch_dict):
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
    
    for attempt in range(max_attempts):
        headers = {
            "Authorization": f"Bearer {API_KEYS[curr_key_idx]}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                
                try:
                    parsed = json.loads(content.strip())
                    if isinstance(parsed, dict) and parsed:
                        # FILTER LAG RAHA HAI (SAVE HONE SE PEHLE)
                        return {k: clean_hindi_words(v) for k, v in parsed.items()}
                except json.JSONDecodeError:
                    print(f"\n⚠️ JSON Decode Error. Retrying...", end="", flush=True)
                    
            elif response.status_code in [429, 413]:
                print(f"\n⚠️ Key #{curr_key_idx + 1} Limit Hit. Switching to next key...", end="", flush=True)
                curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
                time.sleep(2)
                continue
            else:
                print(f"\n⚠️ API ERROR {response.status_code}: {response.text[:100]}", flush=True)
                
        except Exception as e:
            print(f"\n⚠️ Connection Error. Checking next key...", end="", flush=True)
            
        curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
        time.sleep(1)
        
    print("\n❌ CRITICAL: Saari Groq Keys thak chuki hain. Progress auto-save ho rahi hai!")
    sys.exit(1)

# ==========================================
# 5. CORE LOGIC & RESUME SYSTEM
# ==========================================
if not os.path.exists(INPUT_FILE):
    print("\n⚠️ ALERT: Saari Groq Keys thak chuki hain. Progress save karne ke liye gracefully exit kar rahe hain!")
    sys.exit(0)

print(f"📁 Reading source file: {INPUT_FILE}", flush=True)

saved_data = {}
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f: 
        try:
            saved_data = json.load(f)
            saved_data = {k: clean_hindi_words(v) for k, v in saved_data.items()}
            print(f"🔄 RESUME ACTIVE: {len(saved_data)} lines ka backup mil gaya!", flush=True)
        except Exception:
            saved_data = {}

with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f: 
    all_lines = f.readlines()

pending_batch = {}
total_dialogues = sum(1 for line in all_lines if re.search(r'=\s*~(z|w)~', line))
print(f"🎯 Total Dialogues to Translate: {total_dialogues}")

for line in all_lines:
    if re.search(r'=\s*~(z|w)~', line):
        k = line.split('=', 1)[0].strip()
        
        if k not in saved_data:
            pending_batch[k] = line.split('=', 1)[1].strip()
            
        if len(pending_batch) >= BATCH_SIZE:
            current_progress = len(saved_data) + len(pending_batch)
            print(f"\n🚀 Translating with Groq Llama 70B... ({current_progress}/{total_dialogues})", flush=True)
            
            res = translate_batch(pending_batch)
            if res:
                saved_data.update(res)
                with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf: 
                    json.dump(saved_data, cf, ensure_ascii=False, indent=2)
                print("✅ [Saved to Checkpoint]", flush=True)
            
            pending_batch = {}
            time.sleep(1.0) # Lightning Fast Groq

if pending_batch:
    res = translate_batch(pending_batch)
    if res:
        saved_data.update(res)
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as cf: 
            json.dump(saved_data, cf, ensure_ascii=False, indent=2)

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
        
print(f"\n🎉 BOOM! {converted_count}/{total_dialogues} lines Successfully Converted via Groq!", flush=True)
