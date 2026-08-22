# Installs

### Launch the following commands from a bash terminal (in vscode terminal for exmaple)

```bash
# 1. Install the system-level dependency
sudo apt-get install python3-venv python3-pip python3-gnucash libmagic1 python3-tk
python3 -m venv ./venv # creates the environment
source ./venv/bin/activate # activates the py environment
# 2. install env dependencies via pip
pip install tkinterdnd2 pdf2image Pillow pymupdf copykitten python-magic

# 3. Install ollama and its model to have suggestions when filling fields
# for linux :
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b

# for windows :
irm https://ollama.com/install.ps1 | iex
ollama pull gemma3:4b

# if you want to use another model (lighter or heavier go in ./lib/ML.py and modify TEXT_MODEL)
# ollama pull gemma3:1b
```

# Setting parameters

### Go into the * **config** * file and paste the path to your UPSecretrariat folder

### As the second line put the path to the folder you like to use to download all the pdfs you want work with

# Running the code

### launch the main.py and use the GUI
