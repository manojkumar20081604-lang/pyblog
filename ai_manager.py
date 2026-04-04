import os
import sys
from datetime import datetime
import subprocess
from openai import OpenAI

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

FILES_TO_MONITOR = [
    os.path.join(PROJECT_DIR, 'blog_app.py'),
]
TEST_SCRIPT = os.path.join(PROJECT_DIR, 'tests.py')

from blog_app import app, db

class AiUpdateLog(db.Model):
    __tablename__ = 'ai_update_log'
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    code_snippet = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize AI Client
api_key = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=api_key) if api_key else None

def run_tests():
    """Run unit tests and return True if they pass."""
    print("   Running tests to verify changes...")
    # Run the tests.py script
    result = subprocess.run(['python', TEST_SCRIPT], capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✅ Tests Passed.")
        return True
    else:
        print("   ❌ Tests Failed.")
        # Optional: Print stderr to logs if needed
        # print(result.stderr)
        return False

def get_ai_suggestion(code_content):
    """Ask AI to improve the code."""
    if not client:
        print("   Skipping AI: No OPENAI_API_KEY found.")
        return None

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Use gpt-4 if available for better results
            messages=[
                {"role": "system", "content": "You are a senior Python backend developer. Review the following code. If you find bugs, security issues, or simple optimizations, apply them. Return ONLY the valid Python code enclosed in markdown code blocks (```python ... ```). Do not add conversational text. If no changes are needed, return the original code."},
                {"role": "user", "content": code_content}
            ]
        )
        content = response.choices[0].message.content or ""

        # Clean up markdown formatting
        if "```python" in content:
            return content.split("```python")[1].split("```")[0].strip()
        elif "```" in content:
            return content.split("```")[1].split("```")[0].strip()
        return content.strip()
    except Exception as e:
        print(f"   AI Error: {e}")
        return None

def log_update_to_db(filepath, summary, original_code):
    """Logs a successful update to the database."""
    with app.app_context():
        relative_path = os.path.relpath(filepath, PROJECT_DIR)
        log_entry = AiUpdateLog(
            file_path=relative_path,
            summary=summary,
            code_snippet=original_code[:500]
        )
        db.session.add(log_entry)
        db.session.commit()
    print("   📝 Logged update to database.")

def process_file(filepath):
    if not filepath.endswith('.py'):
        return
    print(f"🔍 Analyzing {os.path.basename(filepath)}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        original_code = f.read()

    # 1. Get Suggestion
    improved_code = get_ai_suggestion(original_code)

    if not improved_code or improved_code == original_code:
        print("   No changes suggested.")
        return

    # 2. Create Backup
    backup_path = filepath + ".bak"
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_code)

    # 3. Apply Changes
    print("   ⚡ Applying AI updates...")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(improved_code)

    # 4. Verify with Tests
    if run_tests():
        print(f"   🚀 Update successful for {os.path.basename(filepath)}")
        log_update_to_db(filepath, "AI optimization applied and verified.", original_code)
        os.remove(backup_path) # Cleanup backup
    else:
        print("   ⚠️ Update failed tests. Reverting...")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(original_code)
        os.remove(backup_path)

if __name__ == "__main__":
    print("🤖 Starting AI Autonomous Manager...")
    # In a real scenario, you might loop this or run via cron
    for file in FILES_TO_MONITOR:
        process_file(file)
    print("✨ Maintenance cycle complete.")