import os
import re
import json
import time
import requests

# 1. API Keys Loading
KEYS_ENV = os.environ.get("GROQ_API_KEYS", "")
API_KEYS = [k.strip() for k in KEYS_ENV.split(",") if k.strip()]

if not API_KEYS:
    print("❌ Error: GROQ_API_KEYS Secret nahi mila. GitHub Settings check karein.")
    exit(1)

print(f"✅ Total {len(API_KEYS)} Groq API Keys loaded successfully!")

input_file = "american.oxt"
output_file = "american_roman.oxt"
checkpoint_file = "translation_checkpoint.json"
batch_size = 20
MODEL_NAME = "llama-3.1-8b-instant"

curr_key_idx = 0

# 2. Ultra-Natural Pakistani Roman Urdu System Prompt
SYSTEM_PROMPT = """You are a native Pakistani video game localization expert for Max Payne 3.
Your task is to translate English game dialogues into NATURAL, FLUENT, and DRAMATIC Pakistani Roman Urdu (WhatsApp style).

1. NO LITERAL TRANSLATION (SENTENCE STRUCTURE):
   - DO NOT translate word-for-word literally. Reframe sentences to sound like natural spoken Urdu/Pakistani gaming dialogue.
   - WRONG: "Maine ek badi ladaai li thi... lekin maine pain killers nahin the."
   - RIGHT: "Meri ek bari larai hui thi... lekin mere paas painkillers nahi the."
   - WRONG: "Yeh samay ammo ki talash karne ka tha."
   - RIGHT: "Yeh waqt ammo dhoondne ka tha."

2. CRITICAL VOCABULARY & DICTIONARY RULES (STRICTLY FORBIDDEN HINDI WORDS):
   - NEVER use 'shareer' -> use 'jism' or 'body'
   - NEVER use 'samay' -> use 'waqt' or 'time'
   - NEVER use 'dard nivaarak' -> use 'painkillers'
   - NEVER use 'swasthya' -> use 'sehat' or 'health'
   - NEVER use 'karya' -> use 'kaam'
   - NEVER use 'bhavnaon' -> use 'ehsaas' or 'feelings'
   - NEVER use 'khojne' -> use 'dhoondne'
   - NEVER use 'vishesh' -> use 'khaas'
   - NEVER use 'vah' -> use 'woh'
   - NEVER use 'ladaai li' -> use 'larai hui' or 'jang lari'

3. GAMING & ENGLISH WORDS PRESERVATION:
   - Keep natural English terms AS-IS: 'painkillers', 'ammo', 'guns', 'checkpoint', 'comfort zone', 'plan B', 'time', 'health'.
   - Use gritty, dramatic Pakistani action movie tone (e.g., 'Main yahan fasa hua tha', 'Dushman sar par thay').

4. TECHNICAL RULES:
   - Preserve ALL formatting tags (~z~, ~w~, ~n~, ~a~, ~g~, ~b~) EXACTLY as they appear.
   - Return ONLY a valid JSON object matching the exact input keys."""

# 3. Translation Function with Fail-Safe Key Switch
def translate_batch(batch_dict):
    global curr_key_idx
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = f"Translate these game lines to natural Pakistani Roman Urdu:\n{json.dumps(batch_dict, ensure_ascii=False)}"
    
    max_attempts = len(API_KEYS) * 3 
    
    for attempt in range(max_attempts): 
        payload = {
            "model": MODEL_NAME, 
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}, 
                {"role": "user", "content": prompt}
            ], 
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
                
                if content.startswith('```json'): 
                    content = content[7:-3]
                elif content.startswith('```'): 
                    content = content[3:-3]
                
                try:
                    parsed = json.loads(content.strip())
                    if parsed: return parsed
                except json.JSONDecodeError:
                    print(f"\n⚠️ Format Error. AI response JSON nahi tha. Retrying...", end="", flush=True)
                    
            elif response.status_code in [429, 413]:
                print(f"\n⚠️ Rate Limit! Key #{curr_key_idx + 1} pause hui. Switching key...", end="", flush=True)
                curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
                time.sleep(3)
                continue
                
            else:
                print(f"\n⚠️ ERROR {response.status_code}: {response.text[:100]}", flush=True)
                
        except Exception as e:
            print(f"\n⚠️ Connection Error: {str(e)[:50]}...", end="", flush=True)
            
        curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
        time.sleep(2)
        
    print("\n❌ Laga taar errors. Process pause kar rahe hain.")
    exit(1)

# 4. Main Processing Logic
if os.path.exists(input_file):
    print(f"📁 Reading file: {input_file}", flush=True)
    saved_data = {}
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r", encoding="utf-8") as f: saved_data = json.load(f)
        print(f"🔄 Checkpoint Loaded: {len(saved_data)} lines pehle se completed hain.", flush=True)

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
                    out.write(f"{k} = {saved_data[k]}\n")
                    count += 1
                else: out.write(line)
            else: out.write(line)
            
    print(f"\n🎉 BOOM! SUCCESS! {count} lines Natural Roman Urdu mein convert ho gayin!", flush=True)
else:
    print(f"❌ Error: '{input_file}' file nahi mili.", flush=True)
