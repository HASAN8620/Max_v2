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

# 2. Strict System Prompt (For WhatsApp Style Roman Urdu)
SYSTEM_PROMPT = """You are an expert game dialogue translator.
Translate the English text into natural, conversational, and very easy "WhatsApp-style Roman Urdu" (Latin script).
STRICT RULES:
1. Preserve ALL formatting tags (~z~, ~w~, ~n~, ~a~, ~g~, ~b~) EXACTLY as they appear. Do NOT alter them.
2. Return ONLY a valid JSON object matching the exact input keys. Do not say "Here is the translation".
3. Translate EVERY line into Roman Urdu using English alphabets ONLY. DO NOT return text in original Urdu script (Nastaliq).
4. Tone should be gritty and suited for an action game (e.g., 'Main yahan fasa hua hoon')."""

# 3. Translation Function with Heavy Fail-Safe
def translate_batch(batch_dict):
    global curr_key_idx
    url = "https://api.groq.com/openai/v1/chat/completions"
    prompt = f"Translate these dialogue values to Roman Urdu:\n{json.dumps(batch_dict, ensure_ascii=False)}"
    
    # Max attempts: Har key ko 3 dafa try karega
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
                
                # Cleaning JSON tags
                if content.startswith('```json'): 
                    content = content[7:-3]
                elif content.startswith('```'): 
                    content = content[3:-3]
                
                try:
                    parsed = json.loads(content.strip())
                    if parsed: return parsed
                except json.JSONDecodeError:
                    print(f"\n⚠️ Format Error. AI ne ghalat format bheja. Retrying...", end="", flush=True)
                    
            elif response.status_code == 429:
                print(f"\n⚠️ Rate Limit (Groq API). Key #{curr_key_idx + 1} thak gayi. Key switch kar rahe hain...", end="", flush=True)
                curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
                time.sleep(3)
                continue
                
            else:
                print(f"\n⚠️ ERROR {response.status_code}: {response.text[:100]}", flush=True)
                
        except Exception as e:
            print(f"\n⚠️ Connection Error: {str(e)[:50]}...", end="", flush=True)
            
        # Agar koi aur masla ho toh key badlo aur 2 sec ruko
        curr_key_idx = (curr_key_idx + 1) % len(API_KEYS)
        time.sleep(2)
        
    print("\n❌ Laga taar errors. Script ruk rahi hai taake lines skip na hon.")
    exit(1)

# 4. Main Processing Logic
if os.path.exists(input_file):
    print(f"📁 Reading file: {input_file}", flush=True)
    saved_data = {}
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r", encoding="utf-8") as f: saved_data = json.load(f)
        print(f"🔄 Checkpoint Loaded: {len(saved_data)} lines pehle se mukammal hain.", flush=True)

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
                # Groq ki rate limit bachane ke liye har batch ke baad halka sa pause
                time.sleep(2.0)

    # Aakhri bachi hui lines
    if pending_batch:
        res = translate_batch(pending_batch)
        if res:
            saved_data.update(res)
            with open(checkpoint_file, "w", encoding="utf-8") as cf: 
                json.dump(saved_data, cf, ensure_ascii=False, indent=2)

    # 5. File Rebuilding
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
            
    print(f"\n🎉 BOOM! SUCCESS! {count} lines Roman Urdu mein convert ho gayin!", flush=True)
else:
    print(f"❌ Error: '{input_file}' file nahi mili.", flush=True)
