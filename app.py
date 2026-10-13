import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# הגדרת המפתחות מתוך משתני הסביבה בשרת
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_token_123")

# זיכרון זמני למעקב אחר שלבי השיחה של המשתמשות (User ID -> Stage)
user_sessions = {}

def send_instagram_message(recipient_id, message_data):
    """פונקציה לשליחת הודעה בחזרה לאינסטגרם דרך Meta Graph API"""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": message_data
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """אימות ה-Webhook מול מטא בעת החיבור הראשוני"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return 'Verification token mismatch', 403
    return 'Bad Request', 400

@app.route('/webhook', methods=['POST'])
def handle_messages():
    """טיפול בהודעות נכנסות מאינסטגרם"""
    data = request.get_json()

    if data.get("object") == "page" or data.get("object") == "instagram":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                
                # בדיקה אם התקבלה הודעת טקסט או לחיצה על כפתור Quick Reply
                if "message" in messaging_event:
                    message_obj = messaging_event["message"]
                    user_text = message_obj.get("text", "").strip()
                    
                    # בדיקת שלב המשתמשת בשיחה
                    current_stage = user_sessions.get(sender_id, "START")

                    if current_stage == "START":
                        # שלב 1: הודעת פתיחה + שאלת המטרה עם כפתורי בחירה
                        first_message = {
                            "text": "היייי איזה כיף שהגעת אליי 🥰❤️\n\nספרי לי, מה המטרה העיקרית שלך כרגע?",
                            "quick_replies": [
                                {"content_type": "text", "title": "לרדת באחוזי שומן", "payload": "GOAL_FAT_LOSS"},
                                {"content_type": "text", "title": "לעלות במסת שריר", "payload": "GOAL_MUSCLE"},
                                {"content_type": "text", "title": "לרדת במשקל", "payload": "GOAL_WEIGHT_LOSS"},
                                {"content_type": "text", "title": "להתחזק ולשפר כושר", "payload": "GOAL_FITNESS"},
                                {"content_type": "text", "title": "להרגיש בריאה יותר", "payload": "GOAL_HEALTH"},
                                {"content_type": "text", "title": "כמה מטרות ביחד", "payload": "GOAL_MULTIPLE"},
                                {"content_type": "text", "title": "משהו אחר", "payload": "GOAL_OTHER"}
                            ]
                        }
                        send_instagram_message(sender_id, first_message)
                        user_sessions[sender_id] = "AWAITING_GOAL"

                    elif current_stage == "AWAITING_GOAL":
                        # שלב 2: קבלת התשובה והבקשה למספר טלפון
                        goal_selected = user_text
                        user_sessions[sender_id] = "AWAITING_PHONE"
                        
                        phone_request_message = {
                            "text": "מושלם, תודה ששיתפת אותי! 🌸\nיש לי כמה מסלולי ליווי שונים, וחשוב לי שנבין יחד מה הכי מתאים לך. מה המספר הטלפון שלך כדי שנחזור אליך?"
                        }
                        send_instagram_message(sender_id, phone_request_message)

                    elif current_stage == "AWAITING_PHONE":
                        # שלב 3: קבלת הטלפון והודעת סיום
                        phone_number = user_text
                        print(f"NEW LEAD RECEIVED! User: {sender_id}, Phone: {phone_number}")
                        
                        # ניקוי מצב המשתמשת
                        user_sessions.pop(sender_id, None)

                        thank_you_message = {
                            "text": "תודה רבה! רשמתי את הפרטים, ויועץ מהצוות שלי יצור איתך קשר בהקדם. שיהיה המשך יום מקסים! ✨"
                        }
                        send_instagram_message(sender_id, thank_you_message)

        return "EVENT_RECEIVED", 200
    return "Not Found", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)