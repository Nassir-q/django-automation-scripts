import os
import re
import subprocess
import sys


# This also runs on macOS, Linux and WSL.
IS_WINDOWS = os.name == "nt"
BIN_DIR = "Scripts" if IS_WINDOWS else "bin"
PYTHON_EXE = "python.exe" if IS_WINDOWS else "python"

VALID_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------

def fail(message):
    """Print a clear error and stop with a non-zero exit code.

    The original used a bare sys.exit(), which reports success to the
    shell even when the script failed.
    """
    print(f"\nERROR: {message}\n")
    sys.exit(1)


def run(description, command, cwd=None):
    """Run a command and stop if it fails.

    subprocess.run does not raise on a non-zero exit code, so the
    original kept going after a failure and left a half-built folder.
    """
    print(description)

    try:
        subprocess.run(command, cwd=cwd, check=True)
    except subprocess.CalledProcessError as error:
        fail(f"{description.strip()} failed (exit code {error.returncode}).")
    except FileNotFoundError:
        fail(f"Could not find the program: {command[0]}")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def patch(path, old, new, what):
    """Replace text in a file and confirm the replacement happened.

    Without the confirmation, a change in the Django project template
    would make this a silent no-op: no error, no effect, and a broken
    project you only discover much later.
    """
    with open(path, encoding="utf-8") as handle:
        content = handle.read()

    if old not in content:
        fail(f"Could not patch {what}. Expected to find:\n    {old}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(old, new, 1))


# ------------------------------------------------------------------
# 1. Inputs
# ------------------------------------------------------------------

folder_name = input("Enter the existing day folder name (e.g. Day1): ").strip()

if not folder_name:
    fail("The day folder name cannot be empty.")

if not os.path.isdir(folder_name):
    fail(f"The folder '{folder_name}' does not exist here. Create it first.")

project_name = input("Enter the Django project name (e.g. config): ").strip()

if not VALID_NAME.match(project_name):
    fail(f"'{project_name}' is not a valid project name. Use lowercase "
         "letters, digits and underscores, and do not start with a digit.")

app_names = []

for raw in input("Enter app names, comma separated (e.g. home,accounts): ").split(","):
    name = raw.strip()

    if not name:
        continue

    # startapp rejects an invalid identifier, but the original then
    # carried on and registered the bad name anyway.
    if not VALID_NAME.match(name):
        fail(f"'{name}' is not a valid app name. Use lowercase letters, "
             "digits and underscores, and do not start with a digit.")

    if name == project_name:
        fail(f"An app cannot share the project name '{project_name}'.")

    # Duplicates cause: Application labels aren't unique
    if name not in app_names:
        app_names.append(name)

if not app_names:
    fail("You need at least one app.")


# ------------------------------------------------------------------
# 2. Confirm from the user
# ------------------------------------------------------------------

lab_path = os.path.abspath(os.path.join(folder_name, "lab"))
project_path = os.path.join(lab_path, project_name)

print(f"\nProject  : {project_name}")
print(f"Apps     : {', '.join(app_names)}")
print(f"Location : {project_path}\n")

if input("Create this? (y/n): ").strip().lower() != "y":
    print("Cancelled. Nothing was created.")
    sys.exit(0)

if os.path.exists(project_path):
    fail(f"That project folder already exists: {project_path}")


# ------------------------------------------------------------------
# 3. Virtual environment
# ------------------------------------------------------------------

os.makedirs(lab_path, exist_ok=True)

venv_path = os.path.join(lab_path, "venv")
venv_python = os.path.join(venv_path, BIN_DIR, PYTHON_EXE)

if os.path.exists(venv_python):
    print("[1/6] Reusing the virtual environment already in 'lab'.")
else:
    run("[1/6] Creating the virtual environment...",
        [sys.executable, "-m", "venv", venv_path])

    # venv can report success without producing the interpreter.
    if not os.path.exists(venv_python):
        fail(f"venv finished but python was not found at: {venv_python}")


# ------------------------------------------------------------------
# 4. Django, project and apps
# ------------------------------------------------------------------
# Calling the venv's own python by full path guarantees the packages
# land in this environment, whatever PATH happens to say.

run("[2/6] Upgrading pip...",
    [venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

run("[3/6] Installing Django...",
    [venv_python, "-m", "pip", "install", "django", "--quiet"])

run(f"[4/6] Creating the project '{project_name}'...",
    [venv_python, "-m", "django", "startproject", project_name],
    cwd=lab_path)

for app in app_names:
    run(f"      Creating the app '{app}'...",
        [venv_python, "manage.py", "startapp", app],
        cwd=project_path)


# ------------------------------------------------------------------
# 5. Wiring
# ------------------------------------------------------------------

print("[5/6] Wiring settings.py and urls.py...")

settings_file = os.path.join(project_path, project_name, "settings.py")

patch(settings_file,
      "    'django.contrib.staticfiles',\n]",
      "    'django.contrib.staticfiles',\n\n"
      + "".join(f"    '{app}',\n" for app in app_names) + "]",
      "INSTALLED_APPS")

patch(settings_file,
      "'DIRS': [],",
      "'DIRS': [BASE_DIR / 'templates'],",
      "the TEMPLATES DIRS setting")

with open(settings_file, "a", encoding="utf-8") as handle:
    handle.write("\nSTATICFILES_DIRS = [\n    BASE_DIR / 'static',\n]\n")
    # Without this, turning DEBUG off rejects every request with a 400
    # before you ever reach your own error pages.
    handle.write("\nALLOWED_HOSTS = ['127.0.0.1', 'localhost']\n")

urls_file = os.path.join(project_path, project_name, "urls.py")

patch(urls_file,
      "from django.urls import path",
      "from django.urls import include, path",
      "the import line in urls.py")

patch(urls_file,
      "    path('admin/', admin.site.urls),",
      "    path('admin/', admin.site.urls),\n"
      + "".join(f"    path('{app}/', include('{app}.urls')),\n"
                for app in app_names).rstrip(),
      "urlpatterns")


# startapp does not create urls.py, so we add one with a namespace and
# one working route. The view returns plain text, not a template, so
# nothing here assumes any HTML.
APP_URLS = """from django.urls import path

from . import views

app_name = "__APP__"

urlpatterns = [
    path("", views.index, name="index"),
]
"""

APP_VIEWS = """from django.http import HttpResponse


def index(request):
    return HttpResponse("__APP__ is wired up.")
"""

for app in app_names:
    write(os.path.join(project_path, app, "urls.py"),
          APP_URLS.replace("__APP__", app))

    write(os.path.join(project_path, app, "views.py"),
          APP_VIEWS.replace("__APP__", app))

    # The app name is repeated inside templates/ on purpose: it stops
    # two apps with a same-named template from clobbering each other.
    os.makedirs(os.path.join(project_path, app, "templates", app),
                exist_ok=True)

# Empty, but the settings above already point at them.
os.makedirs(os.path.join(project_path, "templates"), exist_ok=True)
os.makedirs(os.path.join(project_path, "static", "css"), exist_ok=True)

write(os.path.join(project_path, ".gitignore"),
      "venv/\n__pycache__/\n*.pyc\n\ndb.sqlite3\n\n.env\n\n"
      ".vscode/\n.idea/\n\n.DS_Store\nThumbs.db\n")


# ------------------------------------------------------------------
# 6. Migrate and freeze
# ------------------------------------------------------------------

run("[6/6] Running migrations...",
    [venv_python, "manage.py", "migrate", "--verbosity", "0"],
    cwd=project_path)

frozen = subprocess.run([venv_python, "-m", "pip", "freeze"],
                        cwd=project_path, capture_output=True, text=True)

if frozen.returncode != 0:
    fail("pip freeze failed.")

write(os.path.join(project_path, "requirements.txt"), frozen.stdout)


# ------------------------------------------------------------------
# 7. Print what to run next
# ------------------------------------------------------------------
# The original opened a new CMD window here. It is left out on purpose:
# if you already have a terminal in your editor, a second window just
# gets in the way. The commands are printed instead, ready to paste.

if IS_WINDOWS:
    activate = os.path.join("venv", BIN_DIR, "Activate.ps1")
else:
    activate = "source " + os.path.join("venv", BIN_DIR, "activate")

print(f"\nDone. Project created at: {project_path}\n")
print("Next steps, from the 'lab' folder:")
print(f"  cd {os.path.join(folder_name, 'lab')}")
print(f"  {activate}")
print(f"  cd {project_name}")
print("  python manage.py runserver")
print()
print(f"Then open 127.0.0.1:8000/{app_names[0]}/ to confirm the wiring.")
print()
