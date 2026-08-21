# Installs

### Launch the following commands from a bash terminal (in vscode terminal for exmaple)

```bash
# 1. Install the system-level dependency
sudo apt-get install python3-gnucash

# 2. Save your currently installed packages
source .../venv/bin/activate
pip freeze > requirements.txt
deactivate
# 3. Recreate the venv with access to system packages
python3 -m venv --system-site-packages --clear venv
# 4. Reactivate and reinstall your saved packages
source venv/bin/activate
pip install -r requirements.txt

# 5. Install the remaining project dependencies
pip install tkinterdnd2
pip install pdf2image Pillow
pip install pymupdf
pip install copykitten

pip install python-magic
sudo apt-get install libmagic1

sudo apt-get install python3-tk

curl -fsSL https://ollama.com/install.sh | sh
pip install ollama
ollama pull gemma3:1b
```

# Setting parameters

### Go into the * **config** * file and paste the path to your UPSecretrariat folder

### As the second line put the path to the folder you like to use to download all the pdfs you want work with

# Running the code

### launch the main.py and use the GUI
