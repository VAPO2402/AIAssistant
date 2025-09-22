import eel
import speech_recognition as sr
import threading
import json
import os
import base64
import time
import re
import requests
import random
from dotenv import load_dotenv
from gtts import gTTS
from io import BytesIO

eel.init('web')

class AudioAssistant:
    def __init__(self):
        load_dotenv()
        self.setup_audio()
        self.is_listening = False
        self.api_key = None
        self.tts_enabled = True  # Set this to True by default
        self.is_speaking = False
        self.audio_playing = False
        self.stop_requested = False
        self.load_api_key()
        # Interview state
        self.interview_active = False
        self.awaiting_answer = False
        self.current_question_index = -1
        self.collecting_answer = False
        self.collected_transcripts = []
        self.ready_for_next_question = False
        self.latest_proctoring_notes = []
        self.questions_bank = [
            "API",
            "HTML",
            "CSS",
            "JavaScript",
            "Python",
            "Java",
            "Docker",
            "Kubernetes",
            "Linux",
            "Git",
            "Database",
            "Algorithm",
            "Networking",
            "Cloud",
            "DevOps"
        ]
        # Interview config/state
        self.questions_limit = 5
        self.selected_questions = []
        self.total_score_points = 0.0
        self.questions_answered = 0

    def setup_audio(self):
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source)

    def load_api_key(self):
        # Priority: .env -> config.json (Groq only)
        env_key = os.getenv('GROQ_API_KEY')
        if env_key:
            self.set_api_key(env_key)
            return
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.set_api_key(config.get('api_key'))

    def set_api_key(self, api_key):
        self.api_key = api_key
        # Avoid persisting secrets unless explicitly desired; keep in-memory by default

    def delete_api_key(self):
        self.api_key = None
        if os.path.exists('config.json'):
            os.remove('config.json')

    def has_api_key(self):
        return self.api_key is not None

    def toggle_listening(self):
        if not self.api_key:
            return False
        self.is_listening = not self.is_listening
        if self.is_listening:
            threading.Thread(target=self.listen_and_process, daemon=True).start()
        return self.is_listening

    def listen_and_process(self):
        cooldown_time = 2  # Cooldown period in seconds
        last_speak_time = 0
        
        while self.is_listening:
            current_time = time.time()
            if not self.is_speaking and not self.audio_playing and (current_time - last_speak_time) > cooldown_time:
                try:
                    with self.mic as source:
                        # Increase phrase_time_limit to capture longer thoughts and stitch segments
                        audio = self.recognizer.listen(source, timeout=7, phrase_time_limit=12)
                    text = self.recognizer.recognize_google(audio)
                    # If interview is active, treat captured speech as an answer when awaiting
                    if self.interview_active:
                        cleaned_answer = text.strip()
                        if not cleaned_answer:
                            continue
                        # Buffer transcripts while collecting until user clicks Complete Answer
                        if self.awaiting_answer and self.collecting_answer:
                            self.collected_transcripts.append(cleaned_answer)
                            eel.update_ui(f"You: {cleaned_answer}", "")
                            last_speak_time = time.time()
                        else:
                            last_speak_time = time.time()
                    else:
                        # Legacy Q&A mode: only respond to detected questions
                        if self.is_question(text):
                            capitalized_text = text[0].upper() + text[1:]
                            if not capitalized_text.endswith('?'):
                                capitalized_text += '?'
                            eel.update_ui(f"Q: {capitalized_text}", "")
                            self.is_speaking = True
                            self.stop_requested = False
                            response = self.get_ai_response(capitalized_text)
                            eel.update_ui("", f"{response}")
                            self.is_speaking = False
                            last_speak_time = time.time()  # Update the last speak time
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    eel.update_ui(f"An error occurred: {str(e)}", "")
            else:
                time.sleep(0.1)  # Short sleep to prevent busy waiting

    def is_question(self, text):
        # Convert to lowercase for easier matching
        text = text.lower().strip()
        
        # List of question words and phrases
        question_starters = [
            "what", "why", "how", "when", "where", "who", "which",
            "can", "could", "would", "should", "is", "are", "do", "does",
            "am", "was", "were", "have", "has", "had", "will", "shall"
        ]
        
        # Check if the text starts with a question word
        if any(text.startswith(starter) for starter in question_starters):
            return True
        
        # Check for question mark at the end
        if text.endswith('?'):
            return True
        
        # Check for inverted word order (e.g., "Are you...?", "Can we...?")
        if re.match(r'^(are|can|could|do|does|have|has|will|shall|should|would|am|is)\s', text):
            return True
        
        # Check for specific phrases that indicate a question
        question_phrases = [
            "tell me about", "i'd like to know", "can you explain",
            "i was wondering", "do you know", "what about", "how about"
        ]
        if any(phrase in text for phrase in question_phrases):
            return True
        
        # If none of the above conditions are met, it's probably not a question
        return False

    def get_ai_response(self, question):
        try:
            api_key = self.api_key or os.getenv('GROQ_API_KEY') or ""
            if not api_key or not api_key.startswith("gsk_"):
                raise Exception("No valid API key. Provide a Groq API key (gsk_...).")

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            groq_models = [
                "llama-3.1-8b-instant",
                "llama3-8b-8192"
            ]
            last_error = None
            data = None
            for model_id in groq_models:
                payload = {
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": question}
                    ]
                }
                max_attempts = 3
                for attempt in range(max_attempts):
                    resp = requests.post(url, headers=headers, json=payload, timeout=60)
                    status_code = resp.status_code
                    # Retry on 429 or 5xx
                    if status_code == 429 or (500 <= status_code < 600):
                        wait_seconds = min(8, (2 ** attempt)) + random.uniform(0, 0.25)
                        time.sleep(wait_seconds)
                        continue
                    try:
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except requests.exceptions.HTTPError as http_err:
                        try:
                            error_json = resp.json()
                        except Exception:
                            error_json = {"message": resp.text}
                        message_text = str(error_json)
                        last_error = f"HTTP {status_code} from Groq for {model_id}: {message_text}"
                        if "invalid_model" in message_text.lower():
                            # Try next model
                            break
                        # Non-retryable error
                        raise Exception(last_error) from http_err
                if data is not None:
                    break
            if data is None:
                raise Exception(last_error or "No successful response from Groq")
            choices = data.get("choices", []) or []
            first_choice = (choices[0] if len(choices) > 0 else {}) or {}
            message_obj = first_choice.get("message", {}) or {}
            text_response = (message_obj.get("content") or first_choice.get("text") or "").strip()
            if not text_response:
                # Provide a clear message if the model returned no text
                text_response = "No content received from the model. Please try again."
            
            if self.tts_enabled and not self.stop_requested:
                return self.tts_pack(text_response)
            
            return json.dumps({"text": text_response, "audio": None})
        except Exception as e:
            print(f"Error in get_ai_response: {str(e)}")
            return json.dumps({"text": f"Error getting AI response: {str(e)}", "audio": None})

    def tts_pack(self, text):
        try:
            tts = gTTS(text=text)
            buf = BytesIO()
            tts.write_to_fp(buf)
            audio_bytes = buf.getvalue()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            return json.dumps({"text": text, "audio": audio_base64})
        except Exception as e:
            return json.dumps({"text": text, "audio": None})

    # ---- Interview helpers ----
    def start_interview_internal(self):
        self.interview_active = True
        self.current_question_index = -1
        self.awaiting_answer = False
        self.collecting_answer = False
        self.collected_transcripts = []
        # Reset scoring and select randomized questions
        self.total_score_points = 0.0
        self.questions_answered = 0
        # Try to fetch simple random tech questions via AI; fallback to local bank
        self.selected_questions = self._generate_random_questions_via_ai(self.questions_limit)
        if not self.selected_questions:
            bank = list(self.questions_bank)
            random.shuffle(bank)
            self.selected_questions = bank[: min(self.questions_limit, len(bank))]
        # Ensure listening is running
        if not self.is_listening:
            self.is_listening = True
            threading.Thread(target=self.listen_and_process, daemon=True).start()
        return self.next_question_internal()

    def _generate_random_questions_via_ai(self, count):
        try:
            api_key = self.api_key or os.getenv('GROQ_API_KEY') or ""
            if not api_key or not api_key.startswith("gsk_"):
                return []
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            system_prompt = (
                "You generate beginner-friendly single-word tech topics (e.g., 'API', 'Docker', 'HTML'). "
                "Return ONLY a JSON array of single-word strings. No punctuation, no numbering, no explanations."
            )
            user_prompt = f"Generate {count} distinct one-word tech terms."
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", []) or []
            first_choice = (choices[0] if len(choices) > 0 else {}) or {}
            message_obj = first_choice.get("message", {}) or {}
            content = (message_obj.get("content") or first_choice.get("text") or "").strip()
            # Attempt to parse a JSON array from the content
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                try:
                    arr = json.loads(match.group(0))
                    cleaned = []
                    for x in arr:
                        term = str(x).strip()
                        if not term:
                            continue
                        # take only first token and strip punctuation
                        term = term.split()[0]
                        term = re.sub(r"[^A-Za-z0-9+#]+", "", term)
                        if not term:
                            continue
                        cleaned.append(term)
                    # de-duplicate while preserving order
                    seen = set()
                    unique_terms = []
                    for t in cleaned:
                        if t.lower() in seen:
                            continue
                        seen.add(t.lower())
                        unique_terms.append(t)
                    return unique_terms[:count]
                except Exception:
                    return []
            return []
        except Exception:
            return []

    def next_question_internal(self):
        self.current_question_index += 1
        if 0 <= self.current_question_index < len(self.selected_questions):
            q = self.selected_questions[self.current_question_index]
            # Prepend question counter like [1/5] (frontend will display count separately)
            return f"[{self.current_question_index + 1}/{len(self.selected_questions)}] {q}"
        # Completed
        self.interview_active = False
        self.awaiting_answer = False
        return None

    def evaluate_answer(self, answer_text):
        try:
            # Use the actually selected question for the current index
            question_text = ""
            if 0 <= self.current_question_index < len(self.selected_questions):
                question_text = self.selected_questions[self.current_question_index]
            # Append any recent proctoring notes to the context
            proctoring_context = "\n\nProctoring notes: " + "; ".join(self.latest_proctoring_notes) if self.latest_proctoring_notes else ""
            api_key = self.api_key or os.getenv('GROQ_API_KEY') or ""
            if not api_key or not api_key.startswith("gsk_"):
                # Fall back to local shallow feedback
                feedback_text = "Thanks! I'll need an API key to give detailed feedback."
                return json.dumps({"text": feedback_text, "audio": None})

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            system_prompt = (
                "You are a friendly technical interviewer and remote proctor. You receive a basic question, a candidate's answer, "
                "and optional proctoring notes describing movement/cheating indicators. Provide concise feedback in 2-3 sentences: "
                "assess technical correctness, mention key points missing, and give a 1-5 score. If proctoring notes indicate issues "
                "(e.g., multiple faces, face not visible, frequent looking away, frozen camera), add a short 'Proctoring: <notes>' clause. "
                "Keep it simple and encouraging. Strictly format as: Feedback: <text> | Score: <n>/5 | Proctoring: <short note or None>"
            )
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question: {question_text}\nAnswer: {answer_text}{proctoring_context}"}
                ]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", []) or []
            first_choice = (choices[0] if len(choices) > 0 else {}) or {}
            message_obj = first_choice.get("message", {}) or {}
            text_response = (message_obj.get("content") or first_choice.get("text") or "").strip()
            if not text_response:
                text_response = "Thanks for the answer. Here's some brief feedback: [no content]."

            # Extract numeric score and update totals
            try:
                m = re.search(r"Score\s*:\s*(\d+(?:\.\d+)?)\s*/\s*5", text_response, re.IGNORECASE)
                if m:
                    score_val = float(m.group(1))
                    # Clamp between 0 and 5
                    score_val = max(0.0, min(5.0, score_val))
                    self.total_score_points += score_val
                else:
                    # No score parsed; treat as 0
                    pass
            except Exception:
                pass

            # Mark answered count
            self.questions_answered = min(self.questions_answered + 1, len(self.selected_questions) or self.questions_limit)

            if self.tts_enabled:
                return self.tts_pack(text_response)
            return json.dumps({"text": text_response, "audio": None})
        except Exception as e:
            return json.dumps({"text": f"Error generating feedback: {str(e)}", "audio": None})

assistant = AudioAssistant()

@eel.expose
def toggle_listening():
    return assistant.toggle_listening()

@eel.expose
def save_api_key(api_key):
    try:
        assistant.set_api_key(api_key)
        return True
    except Exception as e:
        print(f"Error saving API key: {str(e)}")
        return False

@eel.expose
def delete_api_key():
    try:
        assistant.delete_api_key()
        return True
    except Exception as e:
        print(f"Error deleting API key: {str(e)}")
        return False

@eel.expose
def has_api_key():
    return assistant.has_api_key()

@eel.expose
def toggle_tts():
    assistant.tts_enabled = not assistant.tts_enabled
    return assistant.tts_enabled

@eel.expose
def speaking_ended():
    assistant.is_speaking = False

@eel.expose
def audio_playback_started():
    assistant.audio_playing = True

@eel.expose
def audio_playback_ended():
    assistant.audio_playing = False
    assistant.is_speaking = False
    # If interview feedback just finished and next question is queued, push it now
    try:
        if assistant.interview_active and assistant.ready_for_next_question:
            assistant.ready_for_next_question = False
            nxt = assistant.next_question_internal()
            if nxt:
                eel.update_ui(f"Q: {nxt}", "")
                assistant.awaiting_answer = True
                assistant.collecting_answer = True
                if assistant.tts_enabled:
                    q_audio = assistant.tts_pack(nxt)
                    eel.update_ui("", q_audio)
            else:
                # Completed: show final score summary
                total_q = len(assistant.selected_questions) or assistant.questions_limit
                total_possible = total_q * 5
                total_scored = round(assistant.total_score_points, 2)
                summary = f"Interview completed. Score: {total_scored}/{total_possible}"
                eel.update_ui("", json.dumps({"text": summary, "audio": None}))
    except Exception:
        pass

@eel.expose
def stop_response():
    # Prevent generating any new audio for the current/next response
    assistant.stop_requested = True
    assistant.is_speaking = False
    return True

@eel.expose
def stop_interview():
    try:
        assistant.latest_proctoring_notes = []
        assistant.interview_active = False
        assistant.awaiting_answer = False
        assistant.collecting_answer = False
        assistant.ready_for_next_question = False
        assistant.collected_transcripts = []
        assistant.is_speaking = False
        assistant.audio_playing = False
        return json.dumps({"text": "Interview stopped.", "audio": None})
    except Exception as e:
        return json.dumps({"text": f"Error stopping interview: {str(e)}", "audio": None})

@eel.expose
def stop_tts_playback():
    # Frontend halts audio; backend updates flags
    assistant.audio_playing = False
    assistant.is_speaking = False
    return True

@eel.expose
def ask_question(text):
    try:
        if not isinstance(text, str):
            return json.dumps({"text": "Invalid question.", "audio": None})
        cleaned = text.strip()
        if not cleaned:
            return json.dumps({"text": "Please enter a question.", "audio": None})
        # Normalize capitalization and ensure question mark
        normalized = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()
        if not normalized.endswith('?'):
            # Heuristic: if it looks like a question, append '?'
            if re.match(r'^(what|why|how|when|where|who|which|can|could|would|should|is|are|do|does|am|was|were|have|has|had|will|shall)\b', normalized, re.IGNORECASE):
                normalized += '?'
        eel.update_ui(f"Q: {normalized}", "")
        response = assistant.get_ai_response(normalized)
        eel.update_ui("", f"{response}")
        return response
    except Exception as e:
        return json.dumps({"text": f"Error: {str(e)}", "audio": None})

@eel.expose
def start_interview():
    try:
        first_q = assistant.start_interview_internal()
        if not first_q:
            return json.dumps({"text": "No questions available.", "audio": None})
        # 3-2-1 countdown prompt
        eel.update_ui("", json.dumps({"text": "Interview starts in 3...", "audio": None}))
        time.sleep(1)
        eel.update_ui("", json.dumps({"text": "2...", "audio": None}))
        time.sleep(1)
        eel.update_ui("", json.dumps({"text": "1...", "audio": None}))
        time.sleep(1)
        eel.update_ui(f"Q: {first_q}", "")
        assistant.awaiting_answer = True
        assistant.collecting_answer = True
        assistant.ready_for_next_question = False
        if assistant.tts_enabled:
            q_audio = assistant.tts_pack(first_q)
            eel.update_ui("", q_audio)
        return json.dumps({"text": f"Interview started.", "audio": None})
    except Exception as e:
        return json.dumps({"text": f"Error starting interview: {str(e)}", "audio": None})

@eel.expose
def submit_answer(text):
    try:
        if not assistant.interview_active and not assistant.awaiting_answer:
            return json.dumps({"text": "Start the interview first.", "audio": None})
        cleaned = (text or "").strip()
        if not cleaned:
            return json.dumps({"text": "Please provide an answer.", "audio": None})
        eel.update_ui(f"Your answer: {cleaned}", "")
        feedback = assistant.evaluate_answer(cleaned)
        eel.update_ui("", f"{feedback}")
        assistant.awaiting_answer = False
        # Queue next question after feedback TTS finishes
        assistant.ready_for_next_question = True
        if not assistant.tts_enabled:
            audio_playback_ended()
        return feedback
    except Exception as e:
        return json.dumps({"text": f"Error submitting answer: {str(e)}", "audio": None})

@eel.expose
def complete_answer():
    try:
        if not assistant.interview_active or not assistant.awaiting_answer:
            return json.dumps({"text": "No active question.", "audio": None})
        answer_joined = " ".join(assistant.collected_transcripts).strip()
        if not answer_joined:
            return json.dumps({"text": "I didn't catch an answer. Please try again.", "audio": None})
        eel.update_ui(f"Your answer: {answer_joined}", "")
        assistant.collecting_answer = False
        feedback = assistant.evaluate_answer(answer_joined)
        eel.update_ui("", f"{feedback}")
        assistant.awaiting_answer = False
        assistant.collected_transcripts = []
        assistant.latest_proctoring_notes = []
        # Queue next question after feedback TTS finishes
        assistant.ready_for_next_question = True
        if not assistant.tts_enabled:
            audio_playback_ended()
        return feedback
    except Exception as e:
        return json.dumps({"text": f"Error finalizing answer: {str(e)}", "audio": None})

@eel.expose
def set_proctoring_notes(notes):
    try:
        if isinstance(notes, list):
            # Keep last 10 notes to limit size
            assistant.latest_proctoring_notes = [str(n)[:200] for n in notes][-10:]
            return True
        return False
    except Exception:
        return False

eel.start('index.html', size=(960, 840))