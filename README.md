
# EPUB Translator (DeepL Web Automation)

This tool translates EPUB ebooks using DeepL's free web version. It works with Selenium and undetected ChromeDriver to automate translation in a way that mimics real user behavior. The app comes with a basic GUI, supports checkpointing, and is designed to handle full-length books without losing progress.

## Worklow
![Workflow](https://files.catbox.moe/0wmz2m.png)
## Frontend
![Frontend](https://files.catbox.moe/81tsxt.png)

---

## Features

* **GUI:** Built with Tkinter. Simple interface to select files, choose languages, and start or stop translation.
* **Automated Web Translation:** Uses `undetected-chromedriver` to open Chrome and interact with DeepL like a human.
* **Checkpointing:** Saves progress after every translated chunk so you can resume after interruptions.
* **Chapter-wise Temp Files:** After each chapter, it saves a `_temp.epub` file to prevent data loss.
* **Text Chunking:** Combines small sections into optimal-size chunks (below 5000 characters) for efficient translation.
* **Safe Stopping:** You can click “Stop” at any point. It will finish the current chunk, save progress, and exit cleanly.
* **Basic Formatting Preserved:** Paragraph structure is retained. Dialogue is wrapped in `<em>` tags to improve readability.

---

## How It Works

1. **Reads EPUB:** Identifies the content (XHTML) files inside the EPUB.
2. **Extracts Text:** Pulls out the actual text content to be translated.
3. **Checks Progress:** Skips any text already translated by reading from `translation_checkpoint.json`.
4. **Translates:** Sends chunks of text to DeepL via the web interface.
5. **Saves Progress:** Immediately saves each translated chunk to a checkpoint file.
6. **Writes Temp File:** After each chapter, updates a temporary EPUB file.
7. **Final Output:** Once all content is translated, saves the final EPUB.

If the app crashes or you stop it, it can resume from the last checkpoint or chapter without issues.

---

## Requirements

* Python 3.8 or later
* Google Chrome installed
* A free DeepL account
* ChromeDriver matching your Chrome version

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/rohit12043/EPUB-translator-DeepL.git
cd EPUB-translator-DeepL
```

### 2. Set Up Virtual Environment (Recommended)

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## ChromeDriver Setup

1. Open Chrome and go to `chrome://settings/help` to check your version.
2. Download the corresponding ChromeDriver from the [Chrome for Testing site](https://googlechromelabs.github.io/chrome-for-testing/).
3. Extract `chromedriver.exe` somewhere convenient.
4. Open `gui.py` and find this line in the `EPUBTranslatorGUI` class:

```python
self.chromedriver_path = "chromedriver.exe"
```

5. Replace it with the full path to your `chromedriver.exe`, for example:

```python
self.chromedriver_path = "C:/Users/YourName/Downloads/chromedriver-win64/chromedriver.exe"
```

The script also sets a default Chrome user data folder:

```python
self.profile_path = os.path.join(os.getcwd(), "chrome_profile_deepl")
```

This keeps you logged into DeepL between runs. You can change the folder path if needed.

---

## Running the App

```bash
python main.py
```

### Steps:

1. Click "Browse" to choose the EPUB file.
2. Choose the source language (or leave as Auto) and the target language.
3. Press "Start Translation".
4. Chrome will launch. Log in to your DeepL account if you're not already logged in.
5. Once you're logged in, the translation will start automatically.

You’ll see:

* A progress bar showing how many chapters have been completed.
* Status messages for current tasks.
* A real-time log of what's happening.

To stop the process, click "Stop". The app will finish the current chunk and exit after saving everything.

---

## Customization

You can adjust various options directly in the code if needed.

### In `deepl_translator.py`:

```python
self.retry_attempts = 3         # How many times to retry a failed chunk
self.base_timeout = 10          # Seconds to wait for a response
self.max_input_length = 4950    # Don’t exceed 5000
self.cooldown = 1.5             # Delay between chunks to mimic human behavior
```

### In `epub_handler.py`:

You can skip EPUB content files with names containing certain keywords:

```python
self.excluded_keywords = ['toc', 'nav', 'cover', 'title', 'index', 'info', 'copyright']
```

Add more if needed (e.g., 'dedication', 'appendix').

---

## Common Issues

* **ChromeDriver not found:** Double-check that the path in `gui.py` is correct.
* **Version mismatch:** Make sure the ChromeDriver version matches your installed Chrome.
* **Translation not starting:** You need to manually log in to DeepL in the Chrome window that opens.
* **Daily limit reached:** DeepL free accounts have a usage cap. Wait or switch accounts.
* **Leftover Chrome processes:** If the app is force-closed, Chrome may not shut down. End it from Task Manager or close Chrome manually.

---

## Notes

* The original EPUB is never modified.
* Translation happens in a real browser session using DeepL’s **free web interface**, not the paid API.
* You can resume from any point using the checkpoint JSON or the `_temp.epub` file.
* If you force quit, relaunch and pick the same input EPUB — it will continue from where it left off.

---

## Disclaimer

This project is in a very early stage and is a personal/hobby project. It's been tested on a few books, but may still contain bugs or rough edges. While most common use cases should work fine, unexpected issues might come up depending on the structure of your EPUB or how DeepL behaves.

There’s no fixed roadmap or guaranteed updates. I may continue to improve it when I get time, or leave it as-is. If you find bugs or want to suggest improvements, feel free to open an issue or fork the project.