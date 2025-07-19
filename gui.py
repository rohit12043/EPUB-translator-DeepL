import os
import sys
import logging
import signal
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from epub_handler import EPUBTranslator
from deepl_translator import DeepLTranslator
import time
import random

DEEPL_LANGUAGES = (
    "Bulgarian", "Chinese (simplified)", "Czech", "Danish", "Dutch", "English", 
    "Estonian", "Finnish", "French", "German", "Greek", "Hungarian", "Indonesian", 
    "Italian", "Japanese", "Korean", "Latvian", "Lithuanian", "Norwegian", "Polish", 
    "Portuguese", "Romanian", "Russian", "Slovak", "Slovenian", "Spanish", 
    "Swedish", "Turkish", "Ukrainian", "Vietnamese"
)
DEEPL_SOURCE_LANGUAGES = ("Auto",) + DEEPL_LANGUAGES

class EPUBTranslatorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_gui()
        self.setup_variables()
        self.setup_signal_handlers()
        self.translator = None
        self.epub_translator = None
        self.translation_thread = None
        self.is_translating = False
        self.stop_translation_flag = False
        self.chromedriver_path = "chromedriver.exe"
        self.profile_path = os.path.join(os.getcwd(), "chrome_profile_deepl")
        os.makedirs(self.profile_path, exist_ok=True)
        
    def setup_gui(self):
        """Setup the GUI window."""
        self.root.title("EPUB Translator with DeepL")
        self.root.geometry("700x550") 
        self.root.resizable(True, True)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # --- File Selection Frame ---
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="5")
        file_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Input EPUB:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.input_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.input_path_var, state="readonly").grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(file_frame, text="Browse", command=self.browse_input_file).grid(row=0, column=2)

        ttk.Label(file_frame, text="Output Path:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.output_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.output_path_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
        ttk.Button(file_frame, text="Browse", command=self.browse_output_file).grid(row=1, column=2, pady=(5, 0))

        row += 1

        # --- Language Settings Frame ---
        lang_frame = ttk.LabelFrame(main_frame, text="Language Settings", padding="5")
        lang_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(lang_frame, text="Source Language:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.source_lang_var = tk.StringVar(value="Vietnamese")
        source_combo = ttk.Combobox(lang_frame, textvariable=self.source_lang_var, state="readonly", values=DEEPL_SOURCE_LANGUAGES)
        source_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 20))

        ttk.Label(lang_frame, text="Target Language:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.target_lang_var = tk.StringVar(value="English")
        target_combo = ttk.Combobox(lang_frame, textvariable=self.target_lang_var, state="readonly", values=DEEPL_LANGUAGES)
        target_combo.grid(row=0, column=3, sticky=(tk.W, tk.E))

        lang_frame.columnconfigure(1, weight=1)
        lang_frame.columnconfigure(3, weight=1)

        row += 1
        
        # --- Progress and Log Frames ---
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="5")
        progress_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, sticky=tk.W)
        row += 1

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(row, weight=1) # Make log frame expandable
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=10, width=80, state="disabled")
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        row += 1

        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky=tk.E)
        self.start_button = ttk.Button(button_frame, text="Start Translation", command=self.start_translation)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_translation, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Exit", command=self.exit_application).pack(side=tk.LEFT)

    def setup_variables(self):
        """Setup logging with GUI handler."""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('translation.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget, logger_instance):
                super().__init__()
                self.text_widget = text_widget
                self.logger = logger_instance

            def emit(self, record):
                msg = self.format(record)
                self.text_widget.after(0, lambda: self.log_message(msg))

            def log_message(self, message):
                try:
                    if self.text_widget.winfo_exists():
                        self.text_widget.config(state="normal")
                        self.text_widget.insert(tk.END, message + '\n')
                        self.text_widget.see(tk.END)
                        self.text_widget.config(state="disabled")
                except tk.TclError:
                    self.logger.warning("Attempted to log to a destroyed text widget.")

        gui_handler = GUILogHandler(self.log_text, self.logger)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(gui_handler) # Add to root logger to capture all logs

    def setup_signal_handlers(self):
        """Setup signal handlers for shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.exit_application()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def browse_input_file(self):
        """Browse for input EPUB file."""
        file_path = filedialog.askopenfilename(title="Select EPUB file", filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")])
        if file_path:
            self.input_path_var.set(file_path)
            input_path = Path(file_path)
            output_path = input_path.parent / f"{input_path.stem}_translated.epub"
            self.output_path_var.set(str(output_path))

    def browse_output_file(self):
        """Browse for output EPUB file."""
        file_path = filedialog.asksaveasfilename(title="Save translated EPUB as", defaultextension=".epub", filetypes=[("EPUB files", "*.epub"), ("All files", "*.*")])
        if file_path:
            self.output_path_var.set(file_path)

    def validate_inputs(self):
        """Validate user inputs."""
        if not self.input_path_var.get():
            messagebox.showerror("Error", "Please select an input EPUB file.")
            return False
        if not self.output_path_var.get():
            messagebox.showerror("Error", "Please specify an output path.")
            return False
        if not os.path.exists(self.input_path_var.get()):
            messagebox.showerror("Error", "Input EPUB file does not exist.")
            return False
        
        if not os.path.exists(self.chromedriver_path):
            messagebox.showerror("Error", f"Chromedriver not found at {self.chromedriver_path}. Please check the path.")
            return False
        return True

    def start_translation(self):
        """Start translation process."""
        if not self.validate_inputs():
            return

        if self.is_translating:
            messagebox.showwarning("Warning", "Translation is already in progress.")
            return

        self.stop_translation_flag = False
        self.translation_thread = threading.Thread(target=self.translation_worker, daemon=True)
        self.translation_thread.start()

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.is_translating = True

    def stop_translation(self):
        """Stop translation process."""
        if self.is_translating and not self.stop_translation_flag:
            self.logger.info("Stop button clicked. Signaling worker thread to stop...")
            self.stop_translation_flag = True
            self.update_status("Stopping... Please wait for the current chunk to finish.")
            self.stop_button.config(state="disabled")

    def translation_worker(self):
        """Translation worker thread, adapted for DeepL."""
        browser = None
        try:
            self.update_status("Initializing browser...")
            self.update_progress(0)
            self.log_text.config(state="normal")
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state="disabled")

            temp_epub_translator = EPUBTranslator(
                source_lang=self.source_lang_var.get(),
                target_lang=self.target_lang_var.get()
            )
            browser = temp_epub_translator.setup_browser(self.chromedriver_path)
            del temp_epub_translator
            
            self.epub_translator = EPUBTranslator(
                source_lang=self.source_lang_var.get(),
                target_lang=self.target_lang_var.get(),
                browser=browser
            )

            self.translator = DeepLTranslator(
                driver=browser,
                human_delay=lambda min_val, max_val: time.sleep(random.uniform(min_val, max_val)),
            )

            if not self.translator.ensure_login():
                if self.stop_translation_flag: return
                raise Exception("Failed to log in to DeepL. Login process timed out or was cancelled.")

            self.update_status("Loading EPUB file...")
            input_path = self.input_path_var.get()
            output_path = self.output_path_var.get()

            if not self.epub_translator.load_epub(input_path):
                raise Exception("Failed to load EPUB file")

            success = self.epub_translator.translate_epub(
                output_path=output_path,
                translator=self.translator,
                progress_callback=self.update_progress,
                stop_flag=lambda: self.stop_translation_flag
            )

            if self.stop_translation_flag:
                self.update_status("Translation stopped by user.")
                messagebox.showwarning("Stopped", "Translation was stopped by the user.")
            elif success:
                self.update_status("Translation completed successfully!")
                self.update_progress(100)
                messagebox.showinfo("Success", f"Translation completed successfully!\n\nOutput saved to:\n{output_path}")
            else:
                raise Exception("Translation failed. Check logs for details.")

        except Exception as e:
            if not self.stop_translation_flag:
                self.logger.error(f"Translation worker error: {e}", exc_info=True)
                self.update_status(f"Error: {e}")
                messagebox.showerror("Error", f"An unexpected error occurred during translation: {e}")

        finally:
            if browser:
                try:
                    browser.quit()
                except Exception as e:
                    self.logger.error(f"Error during browser cleanup: {e}")
            self.root.after(0, self.complete_translation)

    def complete_translation(self):
        """Final actions in GUI thread."""
        self.cleanup()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.is_translating = False

    def update_progress(self, value):
        """Update progress bar."""
        try:
            if self.root.winfo_exists():
                self.root.after(0, lambda: self.progress_var.set(value))
        except tk.TclError:
            self.logger.warning("GUI update attempted after window destruction.")

    def update_status(self, message):
        """Update status label."""
        try:
            if self.root.winfo_exists():
                self.root.after(0, lambda: self.status_var.set(message))
        except tk.TclError:
            self.logger.warning("GUI update attempted after window destruction.")
        self.logger.info(message)

    def cleanup(self):
        """Cleanup resources."""
        if self.epub_translator:
            self.epub_translator.cleanup()

    def exit_application(self):
        """Exit application safely."""
        if self.is_translating:
            if messagebox.askyesno("Confirm Exit", "Translation is in progress. Are you sure you want to exit?"):
                self.stop_translation()
                # Give the thread a moment to recognize the stop flag
                self.root.after(1000, self._exit)
        else:
            self._exit()

    def _exit(self):
        """Internal exit function."""
        self.cleanup()
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass
        finally:
            sys.exit(0)

    def run(self):
        """Run the GUI application."""
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        self.root.mainloop()