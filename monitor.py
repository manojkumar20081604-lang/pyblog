import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
# The URL of your deployed application's health check
HEALTH_CHECK_URL = os.environ.get('HEALTH_CHECK_URL', 'https://your-app-name.onrender.com/healthz')

# Email configuration (uses the same variables as your main app)
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
ALERT_RECIPIENT = os.environ.get('ALERT_RECIPIENT', EMAIL_USER)
# ---

def send_alert_email(subject, body):
    """Sends an email alert."""
    if not all([EMAIL_USER, EMAIL_PASS, ALERT_RECIPIENT]):
        print("Email credentials not configured. Cannot send alert.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ALERT_RECIPIENT
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"Alert email sent to {ALERT_RECIPIENT}.")
    except Exception as e:
        print(f"Failed to send alert email: {e}")

def check_service_health():
    """Checks the health of the service and sends an alert on failure."""
    print(f"Checking health of {HEALTH_CHECK_URL}...")
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=10)

        # Check for non-2xx status codes
        if response.status_code >= 300:
            subject = "Service Alert: Application is Down!"
            body = f"The health check for your application failed with status code: {response.status_code}.\n\nURL: {HEALTH_CHECK_URL}\nResponse:\n{response.text}"
            send_alert_email(subject, body)
            return

        # Check the JSON response for database status
        data = response.json()
        if data.get('database') != 'ok':
            subject = "Service Alert: Database Connection Error!"
            body = f"The health check for your application reported a database error.\n\nURL: {HEALTH_CHECK_URL}\nResponse:\n{data}"
            send_alert_email(subject, body)
            return

        print("Service is healthy.")

    except requests.exceptions.RequestException as e:
        subject = "Service Alert: Application is Unreachable!"
        body = f"The health check for your application failed to connect.\n\nURL: {HEALTH_CHECK_URL}\nError: {e}"
        send_alert_email(subject, body)

if __name__ == "__main__":
    check_service_health()