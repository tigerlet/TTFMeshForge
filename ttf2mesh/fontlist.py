import os
import platform
from .core import *


def list_windows_fonts():
    """List fonts on Windows"""
    import winreg
    
    fonts = []
    
    try:
        # Open the fonts registry key
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                            r'Software\Microsoft\Windows NT\CurrentVersion\Fonts')
        
        i = 0
        while True:
            try:
                name, path, _ = winreg.EnumValue(key, i)
                i += 1
                
                if path.endswith('.ttf') or path.endswith('.TTF'):
                    # Check if the font file exists in the system fonts directory
                    font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', path)
                    if os.path.exists(font_path):
                        fonts.append({
                            'name': name,
                            'path': font_path,
                            'is_bold': 'Bold' in name or 'bold' in name.lower(),
                            'is_italic': 'Italic' in name or 'Italic' in name or 'Oblique' in name
                        })
            except OSError:
                break
        
        winreg.CloseKey(key)
    except:
        pass
    
    return fonts


def list_linux_fonts():
    """List fonts on Linux"""
    fonts = []
    
    font_dirs = [
        '/usr/share/fonts',
        '/usr/local/share/fonts',
        os.path.expanduser('~/.fonts'),
        os.path.expanduser('~/.local/share/fonts')
    ]
    
    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        
        for root, dirs, files in os.walk(font_dir):
            for filename in files:
                if filename.lower().endswith('.ttf'):
                    path = os.path.join(root, filename)
                    fonts.append({
                        'name': os.path.splitext(filename)[0],
                        'path': path,
                        'is_bold': 'Bold' in filename or 'bold' in filename.lower(),
                        'is_italic': 'Italic' in filename or 'italic' in filename.lower() or 'Oblique' in filename
                    })
    
    return fonts


def list_macos_fonts():
    """List fonts on macOS"""
    fonts = []
    
    font_dirs = [
        '/Library/Fonts',
        '/System/Library/Fonts',
        os.path.expanduser('~/Library/Fonts')
    ]
    
    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        
        for root, dirs, files in os.walk(font_dir):
            for filename in files:
                if filename.lower().endswith('.ttf'):
                    path = os.path.join(root, filename)
                    fonts.append({
                        'name': os.path.splitext(filename)[0],
                        'path': path,
                        'is_bold': 'Bold' in filename or 'bold' in filename.lower(),
                        'is_italic': 'Italic' in filename or 'italic' in filename.lower() or 'Oblique' in filename
                    })
    
    return fonts


def ttf_list_system_fonts():
    """List all system fonts"""
    os_name = platform.system()
    
    if os_name == 'Windows':
        return list_windows_fonts()
    elif os_name == 'Linux':
        return list_linux_fonts()
    elif os_name == 'Darwin':
        return list_macos_fonts()
    else:
        return []


def ttf_match_font(font_list, family=None, bold=False, italic=False, prefer_bold=False):
    """Match font based on criteria"""
    scores = []
    
    for font in font_list:
        score = 0
        
        # Match family name
        if family:
            family_lower = family.lower()
            font_name_lower = font['name'].lower()
            
            if family_lower in font_name_lower:
                score += 10
            elif any(word in font_name_lower for word in family_lower.split()):
                score += 5
        
        # Match bold
        if font['is_bold'] == bold:
            score += 5
        elif prefer_bold and font['is_bold']:
            score += 3
        
        # Match italic
        if font['is_italic'] == italic:
            score += 5
        
        scores.append((score, font))
    
    # Sort by score (descending) and return best match
    scores.sort(key=lambda x: x[0], reverse=True)
    
    if scores and scores[0][0] > 0:
        return scores[0][1]
    
    return None


def ttf_match_font_by_name(font_name):
    """Match font by name"""
    fonts = ttf_list_system_fonts()
    return ttf_match_font(fonts, family=font_name)


def ttf_font_weight(font):
    """Get font weight"""
    if font is None:
        return 400  # Normal
    
    # Try to get weight from OS/2 table
    if hasattr(font, 'os2') and 'usWeightClass' in font.os2:
        return font.os2['usWeightClass']
    
    # Guess from name
    name = font.names.get('family', '') + ' ' + font.names.get('subfamily', '')
    name_lower = name.lower()
    
    if 'thin' in name_lower:
        return 100
    elif 'extralight' in name_lower:
        return 200
    elif 'light' in name_lower:
        return 300
    elif 'regular' in name_lower or 'normal' in name_lower:
        return 400
    elif 'medium' in name_lower:
        return 500
    elif 'semibold' in name_lower or 'demibold' in name_lower:
        return 600
    elif 'bold' in name_lower:
        return 700
    elif 'extrabold' in name_lower or 'heavy' in name_lower:
        return 800
    elif 'black' in name_lower:
        return 900
    
    return 400


def ttf_font_is_bold(font):
    """Check if font is bold"""
    weight = ttf_font_weight(font)
    return weight >= 700


def ttf_font_is_italic(font):
    """Check if font is italic"""
    if font is None:
        return False
    
    # Check OS/2 table
    if hasattr(font, 'os2') and 'fsSelection' in font.os2:
        if font.os2['fsSelection'].get('italic', False) or font.os2['fsSelection'].get('oblique', False):
            return True
    
    # Check head table
    if hasattr(font, 'head') and 'macStyle' in font.head:
        if font.head['macStyle'].get('italic', False):
            return True
    
    # Check name table
    subfamily = font.names.get('subfamily', '').lower()
    return 'italic' in subfamily or 'oblique' in subfamily


def ttf_font_supports_char(font, char_code):
    """Check if font supports a character"""
    if font is None:
        return False
    
    glyph_idx = ttf_find_glyph(font, char_code)
    return glyph_idx >= 0


def ttf_font_supports_string(font, text):
    """Check if font supports all characters in a string"""
    if font is None:
        return False
    
    for char in text:
        char_code = ord(char)
        if not ttf_font_supports_char(font, char_code):
            return False
    
    return True


def ttf_find_font_for_text(font_list, text):
    """Find font that supports all characters in text"""
    for font_info in font_list:
        result, font = ttf_load_from_file(font_info['path'])
        if result == TTF_DONE:
            if ttf_font_supports_string(font, text):
                return font_info
    
    return None
