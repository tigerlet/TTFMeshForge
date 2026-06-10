import math

EPSILON = 1e-7
PI = math.pi

# Return codes
TTF_DONE = 0
TTF_ERR_NOMEM = 1
TTF_ERR_SIZE = 2
TTF_ERR_OPEN = 3
TTF_ERR_VER = 4
TTF_ERR_FMT = 5
TTF_ERR_NOTAB = 6
TTF_ERR_CSUM = 7
TTF_ERR_UTAB = 8
TTF_ERR_MESHER = 9
TTF_ERR_NO_OUTLINE = 10
TTF_ERR_WRITING = 11

# Quality constants
TTF_QUALITY_LOW = 10
TTF_QUALITY_NORMAL = 20
TTF_QUALITY_HIGH = 50

# Feature flags
TTF_FEATURES_DFLT = 0
TTF_FEATURE_IGN_ERR = 1
TTF_FEATURE_GEN_NORMALS = 2
TTF_FEATURE_MARK_SPLIT = 4
TTF_FEATURE_MARK_SMOOTH = 8

# Weight constants
TTF_WEIGHT_THIN = 100
TTF_WEIGHT_EXTRALIGHT = 200
TTF_WEIGHT_LIGHT = 300
TTF_WEIGHT_NORMAL = 400
TTF_WEIGHT_MEDIUM = 500
TTF_WEIGHT_DEMIBOLD = 600
TTF_WEIGHT_BOLD = 700
TTF_WEIGHT_EXTRABOLD = 800
TTF_WEIGHT_BLACK = 900


class TTFFont:
    def __init__(self):
        self.nchars = 0
        self.nglyphs = 0
        self.chars = []
        self.char2glyph = []
        self.glyphs = []
        self.filename = ""
        self.glyf_csum = 0
        self.ubranges = [0] * 6
        
        # head table fields
        self.head = {
            'rev': 0.0,
            'macStyle': {
                'bold': False,
                'italic': False,
                'underline': False,
                'outline': False,
                'shadow': False,
                'condensed': False,
                'extended': False
            }
        }
        
        # OS/2 table fields
        self.os2 = {
            'xAvgCharWidth': 0.0,
            'usWeightClass': 0,
            'usWidthClass': 0,
            'yStrikeoutSize': 0.0,
            'yStrikeoutPos': 0.0,
            'sFamilyClass': 0,
            'panose': [0] * 10,
            'fsSelection': {
                'italic': False,
                'underscore': False,
                'negative': False,
                'outlined': False,
                'strikeout': False,
                'bold': False,
                'regular': False,
                'utm': False,
                'oblique': False
            },
            'sTypoAscender': 0.0,
            'sTypoDescender': 0.0,
            'sTypoLineGap': 0.0,
            'usWinAscent': 0.0,
            'usWinDescent': 0.0
        }
        
        # name table fields
        self.names = {
            'copyright': "",
            'family': "",
            'subfamily': "",
            'unique_id': "",
            'full_name': "",
            'version': "",
            'ps_name': "",
            'trademark': "",
            'manufacturer': "",
            'designer': "",
            'description': "",
            'url_vendor': "",
            'url_designer': "",
            'license_desc': "",
            'license_url': "",
            'sample_text': ""
        }
        
        # hhea table fields
        self.hhea = {
            'ascender': 0.0,
            'descender': 0.0,
            'lineGap': 0.0,
            'advanceWidthMax': 0.0,
            'minLSideBearing': 0.0,
            'minRSideBearing': 0.0,
            'xMaxExtent': 0.0,
            'caretSlope': 0.0
        }
        
        self.userdata = [None] * 4


class TTFGlyph:
    def __init__(self):
        self.index = 0
        self.symbol = 0
        self.npoints = 0
        self.ncontours = 0
        self.composite = False
        
        # Horizontal metrics
        self.xbounds = [0.0, 0.0]
        self.ybounds = [0.0, 0.0]
        self.advance = 0.0
        self.lbearing = 0.0
        self.rbearing = 0.0
        
        self.outline = None
        self.userdata = [None] * 4


class TTFOutline:
    def __init__(self):
        self.total_points = 0
        self.ncontours = 0
        self.contours = []  # list of TTFContour


class TTFContour:
    def __init__(self):
        self.length = 0
        self.subglyph_id = 0
        self.subglyph_order = 0
        self.points = []  # list of TTFTriPoint


class TTFTriPoint:
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y
        self.spl = False  # point of splitting process
        self.onc = False  # point on curve
        self.shd = False  # smooth shading


class TTFTriMesh:
    def __init__(self):
        self.nvert = 0
        self.nfaces = 0
        self.vert = []  # list of (x, y) tuples
        self.faces = []  # list of (v1, v2, v3) tuples
        self.outline = None


class TTFTriMesh3D:
    def __init__(self):
        self.nvert = 0
        self.nfaces = 0
        self.vert = []  # list of (x, y, z) tuples
        self.faces = []  # list of (v1, v2, v3) tuples
        self.normals = []  # list of (x, y, z) tuples
        self.outline = None


class UnicodeBMPRange:
    def __init__(self, first, last, name):
        self.first = first
        self.last = last
        self.name = name


ubranges = [
    UnicodeBMPRange(0x0000, 0x007F, "Basic Latin"),
    UnicodeBMPRange(0x0080, 0x00FF, "Latin-1 Supplement"),
    UnicodeBMPRange(0x0100, 0x017F, "Latin Extended-A"),
    UnicodeBMPRange(0x0180, 0x024F, "Latin Extended-B"),
    UnicodeBMPRange(0x0250, 0x02AF, "IPA Extensions"),
    UnicodeBMPRange(0x02B0, 0x02FF, "Spacing Modifier Letters"),
    UnicodeBMPRange(0x0300, 0x036F, "Combining Diacritical Marks"),
    UnicodeBMPRange(0x0370, 0x03FF, "Greek and Coptic"),
    UnicodeBMPRange(0x0400, 0x04FF, "Cyrillic"),
    UnicodeBMPRange(0x0500, 0x052F, "Cyrillic Supplement"),
    UnicodeBMPRange(0x0530, 0x058F, "Armenian"),
    UnicodeBMPRange(0x0590, 0x05FF, "Hebrew"),
    UnicodeBMPRange(0x0600, 0x06FF, "Arabic"),
    UnicodeBMPRange(0x0700, 0x074F, "Syriac"),
    UnicodeBMPRange(0x0750, 0x077F, "Arabic Supplement"),
    UnicodeBMPRange(0x0780, 0x07BF, "Thaana"),
    UnicodeBMPRange(0x07C0, 0x07FF, "NKo"),
    UnicodeBMPRange(0x0800, 0x083F, "Samaritan"),
    UnicodeBMPRange(0x0840, 0x085F, "Mandaic"),
    UnicodeBMPRange(0x0860, 0x086F, "Syriac Supplement"),
    UnicodeBMPRange(0x08A0, 0x08FF, "Arabic Extended-A"),
    UnicodeBMPRange(0x0900, 0x097F, "Devanagari"),
    UnicodeBMPRange(0x0980, 0x09FF, "Bengali"),
    UnicodeBMPRange(0x0A00, 0x0A7F, "Gurmukhi"),
    UnicodeBMPRange(0x0A80, 0x0AFF, "Gujarati"),
    UnicodeBMPRange(0x0B00, 0x0B7F, "Oriya"),
    UnicodeBMPRange(0x0B80, 0x0BFF, "Tamil"),
    UnicodeBMPRange(0x0C00, 0x0C7F, "Telugu"),
    UnicodeBMPRange(0x0C80, 0x0CFF, "Kannada"),
    UnicodeBMPRange(0x0D00, 0x0D7F, "Malayalam"),
    UnicodeBMPRange(0x0D80, 0x0DFF, "Sinhala"),
    UnicodeBMPRange(0x0E00, 0x0E7F, "Thai"),
    UnicodeBMPRange(0x0E80, 0x0EFF, "Lao"),
    UnicodeBMPRange(0x0F00, 0x0FFF, "Tibetan"),
    UnicodeBMPRange(0x1000, 0x109F, "Myanmar"),
    UnicodeBMPRange(0x10A0, 0x10FF, "Georgian"),
    UnicodeBMPRange(0x1100, 0x11FF, "Hangul Jamo"),
    UnicodeBMPRange(0x1200, 0x137F, "Ethiopic"),
    UnicodeBMPRange(0x1380, 0x139F, "Ethiopic Supplement"),
    UnicodeBMPRange(0x13A0, 0x13FF, "Cherokee"),
    UnicodeBMPRange(0x1400, 0x167F, "Unified Canadian Aboriginal Syllabics"),
    UnicodeBMPRange(0x1680, 0x169F, "Ogham"),
    UnicodeBMPRange(0x16A0, 0x16FF, "Runic"),
    UnicodeBMPRange(0x1700, 0x171F, "Tagalog"),
    UnicodeBMPRange(0x1720, 0x173F, "Hanunoo"),
    UnicodeBMPRange(0x1740, 0x175F, "Buhid"),
    UnicodeBMPRange(0x1760, 0x177F, "Tagbanwa"),
    UnicodeBMPRange(0x1780, 0x17FF, "Khmer"),
    UnicodeBMPRange(0x1800, 0x18AF, "Mongolian"),
    UnicodeBMPRange(0x18B0, 0x18FF, "Unified Canadian Aboriginal Syllabics Extended"),
    UnicodeBMPRange(0x1900, 0x194F, "Limbu"),
    UnicodeBMPRange(0x1950, 0x197F, "Tai Le"),
    UnicodeBMPRange(0x1980, 0x19DF, "New Tai Lue"),
    UnicodeBMPRange(0x19E0, 0x19FF, "Khmer Symbols"),
    UnicodeBMPRange(0x1A00, 0x1A1F, "Buginese"),
    UnicodeBMPRange(0x1A20, 0x1AAF, "Tai Tham"),
    UnicodeBMPRange(0x1AB0, 0x1AFF, "Combining Diacritical Marks Extended"),
    UnicodeBMPRange(0x1B00, 0x1B7F, "Balinese"),
    UnicodeBMPRange(0x1B80, 0x1BBF, "Sundanese"),
    UnicodeBMPRange(0x1BC0, 0x1BFF, "Batak"),
    UnicodeBMPRange(0x1C00, 0x1C4F, "Lepcha"),
    UnicodeBMPRange(0x1C50, 0x1C7F, "Ol Chiki"),
    UnicodeBMPRange(0x1C80, 0x1C8F, "Cyrillic Extended-C"),
    UnicodeBMPRange(0x1C90, 0x1CBF, "Georgian Extended"),
    UnicodeBMPRange(0x1CC0, 0x1CCF, "Sundanese Supplement"),
    UnicodeBMPRange(0x1CD0, 0x1CFF, "Vedic Extensions"),
    UnicodeBMPRange(0x1D00, 0x1D7F, "Phonetic Extensions"),
    UnicodeBMPRange(0x1D80, 0x1DBF, "Phonetic Extensions Supplement"),
    UnicodeBMPRange(0x1DC0, 0x1DFF, "Combining Diacritical Marks Supplement"),
    UnicodeBMPRange(0x1E00, 0x1EFF, "Latin Extended Additional"),
    UnicodeBMPRange(0x1F00, 0x1FFF, "Greek Extended"),
    UnicodeBMPRange(0x2000, 0x206F, "General Punctuation"),
    UnicodeBMPRange(0x2070, 0x209F, "Superscripts and Subscripts"),
    UnicodeBMPRange(0x20A0, 0x20CF, "Currency Symbols"),
    UnicodeBMPRange(0x20D0, 0x20FF, "Combining Diacritical Marks for Symbols"),
    UnicodeBMPRange(0x2100, 0x214F, "Letterlike Symbols"),
    UnicodeBMPRange(0x2150, 0x218F, "Number Forms"),
    UnicodeBMPRange(0x2190, 0x21FF, "Arrows"),
    UnicodeBMPRange(0x2200, 0x22FF, "Mathematical Operators"),
    UnicodeBMPRange(0x2300, 0x23FF, "Miscellaneous Technical"),
    UnicodeBMPRange(0x2400, 0x243F, "Control Pictures"),
    UnicodeBMPRange(0x2440, 0x245F, "Optical Character Recognition"),
    UnicodeBMPRange(0x2460, 0x24FF, "Enclosed Alphanumerics"),
    UnicodeBMPRange(0x2500, 0x257F, "Box Drawing"),
    UnicodeBMPRange(0x2580, 0x259F, "Block Elements"),
    UnicodeBMPRange(0x25A0, 0x25FF, "Geometric Shapes"),
    UnicodeBMPRange(0x2600, 0x26FF, "Miscellaneous Symbols"),
    UnicodeBMPRange(0x2700, 0x27BF, "Dingbats"),
    UnicodeBMPRange(0x27C0, 0x27EF, "Miscellaneous Mathematical Symbols-A"),
    UnicodeBMPRange(0x27F0, 0x27FF, "Supplemental Arrows-A"),
    UnicodeBMPRange(0x2800, 0x28FF, "Braille Patterns"),
    UnicodeBMPRange(0x2900, 0x297F, "Supplemental Arrows-B"),
    UnicodeBMPRange(0x2980, 0x29FF, "Miscellaneous Mathematical Symbols-B"),
    UnicodeBMPRange(0x2A00, 0x2AFF, "Supplemental Mathematical Operators"),
    UnicodeBMPRange(0x2B00, 0x2BFF, "Miscellaneous Symbols and Arrows"),
    UnicodeBMPRange(0x2C00, 0x2C5F, "Glagolitic"),
    UnicodeBMPRange(0x2C60, 0x2C7F, "Latin Extended-C"),
    UnicodeBMPRange(0x2C80, 0x2CFF, "Coptic"),
    UnicodeBMPRange(0x2D00, 0x2D2F, "Georgian Supplement"),
    UnicodeBMPRange(0x2D30, 0x2D7F, "Tifinagh"),
    UnicodeBMPRange(0x2D80, 0x2DDF, "Ethiopic Extended"),
    UnicodeBMPRange(0x2DE0, 0x2DFF, "Cyrillic Extended-A"),
    UnicodeBMPRange(0x2E00, 0x2E7F, "Supplemental Punctuation"),
    UnicodeBMPRange(0x2E80, 0x2EFF, "CJK Radicals Supplement"),
    UnicodeBMPRange(0x2F00, 0x2FDF, "Kangxi Radicals"),
    UnicodeBMPRange(0x2FF0, 0x2FFF, "Ideographic Description Characters"),
    UnicodeBMPRange(0x3000, 0x303F, "CJK Symbols and Punctuation"),
    UnicodeBMPRange(0x3040, 0x309F, "Hiragana"),
    UnicodeBMPRange(0x30A0, 0x30FF, "Katakana"),
    UnicodeBMPRange(0x3100, 0x312F, "Bopomofo"),
    UnicodeBMPRange(0x3130, 0x318F, "Hangul Compatibility Jamo"),
    UnicodeBMPRange(0x3190, 0x319F, "Kanbun"),
    UnicodeBMPRange(0x31A0, 0x31BF, "Bopomofo Extended"),
    UnicodeBMPRange(0x31C0, 0x31EF, "CJK Strokes"),
    UnicodeBMPRange(0x31F0, 0x31FF, "Katakana Phonetic Extensions"),
    UnicodeBMPRange(0x3200, 0x32FF, "Enclosed CJK Letters and Months"),
    UnicodeBMPRange(0x3300, 0x33FF, "CJK Compatibility"),
    UnicodeBMPRange(0x3400, 0x4DBF, "CJK Unified Ideographs Extension A"),
    UnicodeBMPRange(0x4DC0, 0x4DFF, "Yijing Hexagram Symbols"),
    UnicodeBMPRange(0x4E00, 0x9FFF, "CJK Unified Ideographs"),
    UnicodeBMPRange(0xA000, 0xA48F, "Yi Syllables"),
    UnicodeBMPRange(0xA490, 0xA4CF, "Yi Radicals"),
    UnicodeBMPRange(0xA4D0, 0xA4FF, "Lisu"),
    UnicodeBMPRange(0xA500, 0xA63F, "Vai"),
    UnicodeBMPRange(0xA640, 0xA69F, "Cyrillic Extended-B"),
    UnicodeBMPRange(0xA6A0, 0xA6FF, "Bamum"),
    UnicodeBMPRange(0xA700, 0xA71F, "Modifier Tone Letters"),
    UnicodeBMPRange(0xA720, 0xA7FF, "Latin Extended-D"),
    UnicodeBMPRange(0xA800, 0xA82F, "Syloti Nagri"),
    UnicodeBMPRange(0xA830, 0xA83F, "Common Indic Number Forms"),
    UnicodeBMPRange(0xA840, 0xA87F, "Phags-pa"),
    UnicodeBMPRange(0xA880, 0xA8DF, "Saurashtra"),
    UnicodeBMPRange(0xA8E0, 0xA8FF, "Devanagari Extended"),
    UnicodeBMPRange(0xA900, 0xA92F, "Kayah Li"),
    UnicodeBMPRange(0xA930, 0xA95F, "Rejang"),
    UnicodeBMPRange(0xA960, 0xA97F, "Hangul Jamo Extended-A"),
    UnicodeBMPRange(0xA980, 0xA9DF, "Javanese"),
    UnicodeBMPRange(0xA9E0, 0xA9FF, "Myanmar Extended-B"),
    UnicodeBMPRange(0xAA00, 0xAA5F, "Cham"),
    UnicodeBMPRange(0xAA60, 0xAA7F, "Myanmar Extended-A"),
    UnicodeBMPRange(0xAA80, 0xAADF, "Tai Viet"),
    UnicodeBMPRange(0xAAE0, 0xAAFF, "Meetei Mayek Extensions"),
    UnicodeBMPRange(0xAB00, 0xAB2F, "Ethiopic Extended-A"),
    UnicodeBMPRange(0xAB30, 0xAB6F, "Latin Extended-E"),
    UnicodeBMPRange(0xAB70, 0xABBF, "Cherokee Supplement"),
    UnicodeBMPRange(0xABC0, 0xABFF, "Meetei Mayek"),
    UnicodeBMPRange(0xAC00, 0xD7AF, "Hangul Syllables"),
    UnicodeBMPRange(0xD7B0, 0xD7FF, "Hangul Jamo Extended-B"),
    UnicodeBMPRange(0xD800, 0xDB7F, "High Surrogates"),
    UnicodeBMPRange(0xDB80, 0xDBFF, "High Private Use Surrogates"),
    UnicodeBMPRange(0xDC00, 0xDFFF, "Low Surrogates"),
    UnicodeBMPRange(0xE000, 0xF8FF, "Private Use Area"),
    UnicodeBMPRange(0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
    UnicodeBMPRange(0xFB00, 0xFB4F, "Alphabetic Presentation Forms"),
    UnicodeBMPRange(0xFB50, 0xFDFF, "Arabic Presentation Forms-A"),
    UnicodeBMPRange(0xFE00, 0xFE0F, "Variation Selectors"),
    UnicodeBMPRange(0xFE10, 0xFE1F, "Vertical Forms"),
    UnicodeBMPRange(0xFE20, 0xFE2F, "Combining Half Marks"),
    UnicodeBMPRange(0xFE30, 0xFE4F, "CJK Compatibility Forms"),
    UnicodeBMPRange(0xFE50, 0xFE6F, "Small Form Variants"),
    UnicodeBMPRange(0xFE70, 0xFEFF, "Arabic Presentation Forms-B"),
    UnicodeBMPRange(0xFF00, 0xFFEF, "Halfwidth and Fullwidth Forms"),
    UnicodeBMPRange(0xFFF0, 0xFFFF, "Specials")
]


def find_ubrange(utf16):
    for i, r in enumerate(ubranges):
        if r.first <= utf16 <= r.last:
            return i
    return -1
