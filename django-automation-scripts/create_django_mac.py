import os
import subprocess
import sys

# 1. Get user inputs
folder_name = input(
    "Enter the existing day folder name (e.g., Day1): ").strip()
project_name = input(
    "Enter the Django project name (e.g., config or myproject): ").strip()
app_name = input("Enter the app name (e.g., home or accounts): ").strip()

# Check if the day folder already exists
if not folder_name or not os.path.exists(folder_name):
    print(
        f"Error: The folder '{folder_name}' does not exist here. Please make sure it's created.")
    sys.exit()

if not project_name or not app_name:
    print("Error: Project and App names cannot be empty.")
    sys.exit()

# 2. Create the 'lab' subfolder inside the day folder
lab_path = os.path.join(folder_name, "lab")
os.makedirs(lab_path, exist_ok=True)
print(
    f"\n[1/4] Created 'lab' folder inside '{folder_name}'. Setting up virtual environment...")

venv_path = os.path.join(lab_path, "venv")
subprocess.run([sys.executable, "-m", "venv", venv_path])

# 3. Define macOS paths for the virtual environment
python_in_venv = os.path.join(venv_path, "bin", "python")
django_admin = os.path.join(venv_path, "bin", "django-admin")

print("[2/4] Upgrading pip and installing Django...")
subprocess.run([python_in_venv, "-m", "pip", "install", "--upgrade", "pip"])
subprocess.run([python_in_venv, "-m", "pip", "install", "django"])

print(f"[3/4] Creating Django project ({project_name}) inside 'lab'...")
subprocess.run([django_admin, "startproject", project_name], cwd=lab_path)

print(f"[4/4] Creating app ({app_name}) inside the project...")
project_path = os.path.join(lab_path, project_name)
subprocess.run([python_in_venv, "manage.py",
               "startapp", app_name], cwd=project_path)

print(
    f"\n[✔] Done! 'lab' folder created inside '{folder_name}' with virtual environment, project '{project_name}', and app '{app_name}' successfully set up.")
