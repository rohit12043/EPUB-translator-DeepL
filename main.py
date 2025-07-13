import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path
from epub_handler import EPUBTranslator
from gui import EPUBTranslatorGUI
from deepl_translator import DeepLTranslator
import time 
import random 
import os

def setup_logging():
    """Set up logging configuration"""
    # Remove all the default root handlers.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
        
    # Setup custom logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('translation.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('deepl').setLevel(logging.DEBUG)
    logging.getLogger('epub_handler').setLevel(logging.DEBUG)
    logging.getLogger('undetected_chromedriver').setLevel(logging.WARNING)

logger = setup_logging

def run_gui():
    """Runs the EPUB Translator with a Graphical User Interface."""
    try:
        logger.info('Checking availibilty of Tkinter...')
        test_root = tk.Tk()
        test_root.withdraw()
        test_root.destroy()
        logger.info('Tkinter is available')
        
        logger.info('Initializing the GUI')
        app = EPUBTranslatorGUI()
        logger('Starting GUI application...')
        app.run()
    except tk.TclError as e:
        logger.error(f"Tkinter error: {e}", exc_info=True)
        print(f"\nError: Tkinter failed to initialize - {e}")
        sys.exit(1)

def run_cli(input_file: str, output_path: str, source_lang: str, target_lang: str, chromedriver_path: str):
    """Runs the EPUB Translator in command-line mode."""
    try:
        logger.info(f"Starting CLI translation for input: '{input_file}' to output: '{output_path}")
        
        if not Path(input_file).exists():
            raise FileNotFoundError(f"Input file does not exist: {input_file}")
        
        
        
        if not Path(chromedriver_path).exists():
            raise FileNotFoundError(f"Chromedriver not found at: {Path(chromedriver_path).absolute()}. Please provide the full path.")
        
        logger.info(f"Using Chromedriver: {Path(chromedriver_path).absolute()}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        epub_translator = EPUBTranslator(source_lang=source_lang, target_lang=target_lang)
        browser = None
        
        try:
            browser = epub_translator.setup_browser(str(Path(chromedriver_path)))
            
            translator = DeepLTranslator(driver=browser, human_delay = lambda min_val, max_val: time.sleep(random.uniform(min_val, max_val)))
            logger.info("CLI mode: waiting for manual login to DeepL. Please log in in the browser.")
            
            if not(translator.ensure_login()):
                raise Exception("Failed to detect DeepL login in CLI mode.")
            logger.info("Login detected. Starting translation.")
            
            logger.info(f"Loading EPUB file: {input_file}")
            
            if not epub_translator.load_epub(input_file):
                raise Exception("Failed to load EPUB file.")
            
            def progress_callback(progress):
                print(f"Progress: {progress:.1f}%", end='\r', flush=True)
                
            logger.info("starting EPUB translation Process...")
            success = epub_translator.translate_epub(
                output_path=output_path,
                translator=translator,
                progress_callback=progress_callback,
                stop_flag=lambda: False
            )
            
            print()
            
            if(success):
                logger.info(f"translation completed succesfully, Output file:{output_path}")
                print(f"Translation completed successfully: {output_path}")
            else:
                raise Exception("Translation failed.")
        
        finally:
            if browser:
                try:
                    browser.quit()
                except Exception as e:
                    logger.error(f"Error during browser cleanup in CLI mode: {e}")
                    epub_translator.cleanup()
                    
    except Exception as e:
        logger.error(f"CLI translation failed: {e}", exc_info=True)
        print(f"\nError: CLI translation failed - {e}\nCheck 'translation.log' for detailed information.")
        sys.exit(1)
        
def main():
    """Main etry point for the EPUB Translator application."""
    parser = argparse.ArgumentParser(description="translate EPUB files using DeepL")
    parser.add_argument('--input', help="Input EPUB file path (required in --no-gui mode)")
    parser.add_argument('--output', help="Output EPUB file path (required in --no-gui mode)")
    parser.add_argument('--source-lang', default="Korean", help="Source language (e.g., 'Korean', 'English', 'Auto'). Default: Korean")
    parser.add_argument('--target-lang', default="English", help="Target language (e.g., 'English', 'Vietnamese'). Default: English")
    parser.add_argument('--chromedriver', default="chromedriver.exe", help="Path to Chromedriver executable.")
    parser.add_argument('--no-gui', action='store_true', help="Run in command-line mode instead of GUI.")
                
    args = parser.parse_args()
    
    if args.no_gui:
        if not args.input or not args.output:
            parser.error("--input and --output are required when using --no-gui mode.")
        run_cli(args.input, args.output, args.source_lang, args.target_lang, args.chromedriver)
    else:
        run_gui()
        
if __name__ == "__main__":
    main()
        
    