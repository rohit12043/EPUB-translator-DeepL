import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

class TranslatorBase:
    def extract_whitespace_info(self, text: str) -> Dict:
        """Extract whitespace details from text."""
        
        if not text:
            logger.debug("Empty input text, returning default whitespace info.")
            return {
                'original_length': 0,
                'normalized': '',
                'paragraph_breaks': [],
                'line_breaks': [],
                'has_paragraphs': False,
                'breaks': [],
                'leading_spaces': '',
                'trailing_spaces': '',
                'extra_spaces': {}
            }
            
        leading_spaces = re.match(r'^(\s*)', text).group(1) or ''
        trailing_spaces = re.search(r'(\s*)$', text).group(1) or ''
        extra_spaces = {m.start(): m.group() for m in re.finditer(r' {2,}', text)}
        normalized = re.sub(r'\s+', ' ', text.strip())
        
        paragraph_breaks = []
        line_breaks = []
        breaks = []
        current_pos = 0
        last_pos = 0
        
        for match in re.finditer(r'(\n\s*\n|\n)', text):
            start = match.start()
            segment = text[last_pos:start]
            if segment:
                current_pos += len(segment)
            break_type = 'paragraph' if match.group(0).strip() else 'line'
            breaks.append({'position': current_pos, 'type': break_type})
            if break_type == 'paragraph':
                paragraph_breaks.append(current_pos)
                current_pos += 2
            else:
                line_breaks.append(current_pos)
                current_pos += 1
            last_pos = match.end()

        if last_pos < len(text):
            current_pos += len(text[last_pos:])

        result = {
            'original_length': len(text),
            'normalized': normalized,
            'paragraph_breaks': paragraph_breaks,
            'line_breaks': line_breaks,
            'has_paragraphs': len(paragraph_breaks) > 0,
            'breaks': breaks,
            'leading_spaces': leading_spaces,
            'trailing_spaces': trailing_spaces,
            'extra_spaces': extra_spaces
        }
        logger.debug(f"Extracted whitespace info: {len(paragraph_breaks)} paragraph breaks, "
                     f"{len(line_breaks)} line breaks, {len(extra_spaces)} extra spaces, "
                     f"original_length={len(text)}")
        return result
    
    def reconstruct_whitespace(self, translated_text: str, whitespace_info: Dict) -> str:
        """Reconstruct text with original whitespace."""
        try:
            if not translated_text.strip():
                logger.debug("Empty translated text, returning with leading/trailing spaces")
                return whitespace_info.get('leading_spaces', '') + whitespace_info.get('trailing_spaces', '')

            if not whitespace_info.get('has_paragraphs', False):
                logger.debug("No paragraph breaks, applying fallback reconstruction")
                sentences = re.split(r'(?<=[.!?])\s+', translated_text)
                chunks = [sentences[i: i + 5] for i in range (0, len(sentences), 5)]
                reconstructed = '\n\n'.join(' '.join(chunk) for chunk in chunks)
                reconstructed = (whitespace_info.get('leading_spaces', '') +
                                reconstructed +
                                whitespace_info.get('trailing_spaces', ''))
                logger.debug(f"Fallback reconstruction: {len(reconstructed)} chars")
                return reconstructed

            translated_segments = [s.strip() for s in re.split(r'\n\s*\n|\n', translated_text) if s.strip()]
            if not translated_segments:
                logger.warning("No valid translated segments, returning with leading/trailing spaces")
                return (whitespace_info.get('leading_spaces', '') +
                        translated_text +
                        whitespace_info.get('trailing_spaces', ''))

            result = []
            segment_index = 0
            current_pos = 0
            breaks = sorted(whitespace_info.get('breaks', []), key=lambda x: x['position'])
            
            for break_info in breaks:
                while(segment_index < len(translated_segments) and (current_pos <= break_info['position'] or not breaks)):
                    result.append(translated_segments[segment_index])
                    current_pos += len(translated_segments[segment_index])
                    segment_index += 1
                if break_info['type'] == 'paragraph':
                    result.append('\n\n')
                    current_pos += 2
                elif break_info['type'] == 'line':
                    result.append('\n')
                    current_pos += 1
                    
            while segment_index < len(translated_segments):
                result.append(translated_segments[segment_index])
                segment_index += 1
                
            final_text = ''.join(result)
            extra_spaces = whitespace_info.get('extra_spaces', {})

            for pos, spaces in sorted(extra_spaces.items(), reverse=True):
                if pos <= len(final_text):
                    final_text = final_text[:pos] + spaces + final_text[pos:]

            final_text = (whitespace_info.get('leading_spaces', '') +
                          final_text +
                          whitespace_info.get('trailing_spaces', ''))
            logger.debug(f"Reconstructed whitespace: {len(final_text)} chars, "
                         f"{len(breaks)} breaks applied, {segment_index} segments used, "
                         f"{len(extra_spaces)} extra spaces applied")
            return final_text
        except Exception as e:
            logger.error(f"Whitespace reconstruction failed: {e}")
            return (whitespace_info.get('leading_spaces', '') +
                    translated_text +
                    whitespace_info.get('trailing_spaces', ''))    
