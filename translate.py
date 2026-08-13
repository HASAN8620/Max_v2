import os
import re
import json
import time
import requests

# 1. API Keys Loading
KEYS_ENV = os.environ.get("GROQ_API_KEYS", "")
API_KEYS = [k.strip() for k in KEYS_ENV.split(",") if k.strip()]

if not API_KEYS:
    print("❌ Error: GROQ_API_KEYS Secret nahi mila.")
    exit(1)

print(f"✅ Total {len(API_KEYS)} Groq API Keys loaded successfully!")

input_file = "american.oxt"
output_file = "american_roman.oxt"
checkpoint_file = "translation_checkpoint.json"
batch_size = 20
MODEL_NAME = "llama-3.1-8b-instant"

curr_key_idx = 0

# 2. Strict Positive Prompt (No Negative/Wrong Examples)
SYSTEM_PROMPT = """You are a native Pakistani video game localization expert for Max Payne 3.
Translate English game dialogues into natural, dramatic, spoken Pakistani Roman Urdu (WhatsApp style).

RULES:
1. Translate into natural spoken Pakistani dialogue tone.
2. Vocabulary to use: 'waqt' (time), 'jism' (body), 'painkillers', 'sehat' (health), 'kaam' (work), 'dhoondne' (find), 'larai' (fight), 'bari' (big).
3. Keep gaming terms in English: 'painkillers', 'ammo', 'guns', 'checkpoint', 'comfort zone', 'health', 'plan B'.
4. Keep all formatting tags (~z~, ~w~, ~n~, ~a~, ~g~, ~b~) EXACTLY as they appear."""

# 3. Fail-Safe Python Auto-Corrector (Hinglish/Hindi Elimination)
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
    r'\bkhata hai\b': 'khauf hai',
    r'\btaraab\b': 'pareshan'
}

def clean_hindi_words(text):
    if not isinstance(text, str):
        return text
    for pattern, replacement in HINDI_TO_URDU.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# 4. Translation Function
def translate_batch(batch_dict):
    global curr_key_idx
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    prompt = f"Translate these JSON values to natural Pakistani Roman Urdu:\n{json.dumps(batch_dict, ensure_ascii=False)}"
    
    max_attempts = len(API_KEYS) * 3 
    
    for attempt in range(max_attempts): 
        payload = {
            "model": MODEL_NAME, 
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}, 
                {"role": "user", "content": prompt}
            ], 
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        
        headers = {
            "Authorization": f"Bearer {API_KEYS[curr_key_idx]}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=40)
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                
                try:
                    clean_content = content.strip()
                    if clean_content.startswith("```json"): clean_content = clean_content[7:]
                    if clean_content.startswith("```"): clean_content = clean_content[3:]
                    if clean_content.endswith("```"): clean_content = clean_content[:-3]
                    
                    parsed = json.loads(clean_content.strip())
                    if isinstance(parsed, dict) and parsed:
                        # 🚀 Python Auto-Correction Engine Rules Execution
                        cleaned_parsed = {k: clean_hindi_words(v) for k, v in parsed.items()}
                        return cleaned_parsed
                except json.JSONDecodeError:
                    print(f"\n⚠️ Format Error. Retrying...", end="", flush=True)
                    
            elif response.status_code in [429, 413]:
                print(f"\n⚠️ Rate Limit! Key #{curr_key_idx + 1} pause. Switching key...", end="", flush=True)
                curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
                time.sleep(3)
                continue
                
            else:
                print(f"\n⚠️ ERROR {response.status_code}: {response.text[:100]}", flush=True)
                
        except Exception as e:
            print(f"\n⚠️ Connection Error: {str(e)[:50]}...", end="", flush=True)
            
        curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
        time.sleep(2)
        
    print("\n❌ Errors. Pause.")
    exit(1)

# 5. Main Processing Logic
if os.path.exists(input_file):
    print(f"📁 Reading file: {input_file}", flush=True)
    
    # Force fresh run by wiping old checkpoint in memory if needed
    saved_data = {}
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r", encoding="utf-8") as f: 
            try:
                saved_data = json.load(f)
                # Clean existing checkpoint data as well!
                saved_data = {k: clean_hindi_words(v) for k, v in saved_data.items()}
                print(f"🔄 Checkpoint Loaded & Auto-Corrected: {len(saved_data)} lines.", flush=True)
            except Exception:
                saved_data = {}

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f: all_lines = f.readlines()
    pending_batch = {}
    total = 0

    for line in all_lines:
        if re.search(r'=\s*~(z|w)~', line):
            total += 1
            k = line.split('=', 1)[0].strip()
            if k not in saved_data:
                pending_batch[k] = line.split('=', 1)[1].strip()
                
            if len(pending_batch) >= batch_size:
                print(f"\n🚀 Translating batch... ({len(saved_data)}/{total})", flush=True)
                res = translate_batch(pending_batch)
                if res:
                    saved_data.update(res)
                    with open(checkpoint_file, "w", encoding="utf-8") as cf: 
                        json.dump(saved_data, cf, ensure_ascii=False, indent=2)
                    print("✅ [Batch Saved Successfully]", flush=True)
                pending_batch = {}
                time.sleep(2.0)

    if pending_batch:
        res = translate_batch(pending_batch)
        if res:
            saved_data.update(res)
            with open(checkpoint_file, "w", encoding="utf-8") as cf: 
                json.dump(saved_data, cf, ensure_ascii=False, indent=2)

    print("\n🔨 Rebuilding american_roman.oxt file...", flush=True)
    count = 0
    with open(output_file, "w", encoding="utf-8") as out:
        for line in all_lines:
            if re.search(r'=\s*~(z|w)~', line):
                k = line.split('=', 1)[0].strip()
                if k in saved_data:
                    clean_text = clean_hindi_words(saved_data[k])
                    out.write(f"{k} = {clean_text}\n")
                    count += 1
                else: out.write(line)
            else: out.write(line)
            
    print(f"\n🎉 BOOM! SUCCESS! {count} lines Pure Pakistani Roman Urdu mein convert ho gayin!", flush=True)
else:
    print(f"❌ Error: '{input_file}' file nahi mili.", flush=True)
