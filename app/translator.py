from deep_translator import GoogleTranslator

async def translate_to_english(text: str) -> str:
    """
    Translate text from any detected language to English.
    If the text is already in English, returns it as is.
    """
    try:
        
        # Translate to English
        translator = GoogleTranslator(source="auto", target='en')
        translated_text = translator.translate(text)
        
        return translated_text
    except Exception as e:
        # If any error occurs in translation, return the original text
        print(f"Translation error: {e}")
        return text