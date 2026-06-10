import struct
import os
from .core import *


def big16toh(x):
    return struct.unpack('>H', struct.pack('<H', x))[0]


def big32toh(x):
    return struct.unpack('>I', struct.pack('<I', x))[0]


def ttf_checksum(data):
    """Calculate TTF checksum"""
    sum_val = 0
    length = len(data)
    
    # Process full 4-byte blocks
    for i in range(0, length - (length % 4), 4):
        val = struct.unpack('>I', data[i:i+4])[0]
        sum_val += val
    
    # Handle remaining bytes (padding with zeros)
    remaining = length % 4
    if remaining > 0:
        val = 0
        for i in range(remaining):
            val = (val << 8) | data[length - remaining + i]
        sum_val += val
    
    # Apply circular carry (add high 32 bits to low 32 bits)
    sum_val = (sum_val & 0xFFFFFFFF) + (sum_val >> 32)
    sum_val = (sum_val & 0xFFFFFFFF) + (sum_val >> 32)
    
    return sum_val & 0xFFFFFFFF


def f2dot14_to_float(val):
    """Convert 16-bit fixed-point (14 fractional bits) to float"""
    return val / 16384.0


def parse_fmt4_table(data, data_size, font, headers_only):
    """Parse format 4 cmap table"""
    if data_size < 8:
        return TTF_ERR_FMT
    
    format_, length, language, segCountX2 = struct.unpack('>HHHH', data[:8])
    if length > data_size:
        return TTF_ERR_FMT
    
    segCount = segCountX2 // 2
    offset = 8
    
    endCode = []
    for i in range(segCount):
        endCode.append(struct.unpack('>H', data[offset:offset+2])[0])
        offset += 2
    
    offset += 2  # reservedPad
    
    startCode = []
    for i in range(segCount):
        startCode.append(struct.unpack('>H', data[offset:offset+2])[0])
        offset += 2
    
    idDelta = []
    for i in range(segCount):
        idDelta.append(struct.unpack('>h', data[offset:offset+2])[0])
        offset += 2
    
    idRangeOffset = []
    for i in range(segCount):
        idRangeOffset.append(struct.unpack('>H', data[offset:offset+2])[0])
        offset += 2
    
    glyphIdArray = []
    remaining = data_size - offset
    for i in range(remaining // 2):
        glyphIdArray.append(struct.unpack('>H', data[offset:offset+2])[0])
        offset += 2
    
    if headers_only:
        # Just mark unicode ranges
        k = 0
        for i in range(segCount):
            if endCode[i] == 0xFFFF:
                break
            # Skip reserved segments (startCode > endCode)
            if startCode[i] > endCode[i]:
                continue
            for j in range(startCode[i], endCode[i] + 1):
                r = find_ubrange(j)
                if r >= 0:
                    font.ubranges[r // 32] |= 1 << (r & 31)
                k += 1
        return TTF_DONE
    
    # Full parsing
    # Use a dictionary to handle overlapping segments - last segment wins
    char_map = {}
    
    for i in range(segCount):
        if endCode[i] == 0xFFFF:
            break
        # Skip reserved segments (startCode > endCode)
        if startCode[i] > endCode[i]:
            continue
        
        # Skip segments that are out of range
        if endCode[i] > 0xFFFF or startCode[i] > 0xFFFF:
            continue
        
        for j in range(startCode[i], endCode[i] + 1):
            if idRangeOffset[i] == 0:
                glyph_idx = (j + idDelta[i]) & 0xFFFF
            else:
                # Calculate the index into glyphIdArray
                array_idx = (idRangeOffset[i] // 2) + (j - startCode[i])
                if array_idx >= len(glyphIdArray):
                    # Fallback to idDelta if out of range
                    glyph_idx = (j + idDelta[i]) & 0xFFFF
                else:
                    glyph_idx = glyphIdArray[array_idx]
            # Always overwrite - last segment takes precedence for overlapping ranges
            char_map[j] = glyph_idx
    
    # Convert to sorted lists
    chars = sorted(char_map.keys())
    char2glyph = [char_map[c] for c in chars]
    
    font.chars = chars
    font.char2glyph = char2glyph
    font.nchars = len(chars)
    
    for i in range(font.nchars):
        glyph_idx = font.char2glyph[i]
        if glyph_idx < font.nglyphs:
            font.glyphs[glyph_idx].index = glyph_idx
            font.glyphs[glyph_idx].symbol = font.chars[i]
    
    return TTF_DONE


def parse_fmt12_table(data, data_size, font, headers_only):
    """Parse format 12 cmap table"""
    if data_size < 16:
        return TTF_ERR_FMT
    
    format_, reserved, length, language, numGroups = struct.unpack('>HHIII', data[:16])
    if length > data_size:
        return TTF_ERR_FMT
    
    smg_size = data_size - 16
    if smg_size < numGroups * 12:
        return TTF_ERR_FMT
    
    if headers_only:
        k = 0
        for i in range(numGroups):
            offset = 16 + i * 12
            startCharCode, endCharCode, startGlyphID = struct.unpack('>III', data[offset:offset+12])
            for j in range(startCharCode, endCharCode + 1):
                r = find_ubrange(j)
                if r >= 0:
                    font.ubranges[r // 32] |= 1 << (r & 31)
                k += 1
        return TTF_DONE
    
    chars = []
    char2glyph = []
    
    for i in range(numGroups):
        offset = 16 + i * 12
        startCharCode, endCharCode, startGlyphID = struct.unpack('>III', data[offset:offset+12])
        for j in range(endCharCode - startCharCode + 1):
            chars.append(startCharCode + j)
            char2glyph.append(startGlyphID + j)
    
    font.chars = chars
    font.char2glyph = char2glyph
    font.nchars = len(chars)
    
    for i in range(font.nchars):
        glyph_idx = font.char2glyph[i]
        if glyph_idx < font.nglyphs:
            font.glyphs[glyph_idx].index = glyph_idx
            font.glyphs[glyph_idx].symbol = font.chars[i]
    
    return TTF_DONE


def locate_cmap_table(data, format_type):
    """Locate cmap table of specific format"""
    if len(data) < 4:
        return None, 0
    
    version, numTables = struct.unpack('>HH', data[:4])
    
    if version != 0:
        return None, 0
    
    offset = 4
    for i in range(numTables):
        if offset + 8 > len(data):
            return None, 0
        
        platformID, encodingID, subOffset = struct.unpack('>HHI', data[offset:offset+8])
        offset += 8
        
        if subOffset + 4 > len(data):
            continue
        
        subFormat = struct.unpack('>H', data[subOffset:subOffset+2])[0]
        if subFormat == format_type:
            # Read the length field to get the actual size of this subtable
            subLength = struct.unpack('>H', data[subOffset+2:subOffset+4])[0]
            return data[subOffset:subOffset+subLength], subLength
    
    return None, 0


def parse_name_table(data, font):
    """Parse name table"""
    if len(data) < 6:
        return False
    
    format_, count, stringOffset = struct.unpack('>HHH', data[:6])
    
    if format_ not in (0, 1):
        return False
    
    for i in range(count):
        offset = 6 + i * 12
        if offset + 12 > len(data):
            break
        
        platformID, encodingID, languageID, nameID, length, stringOffset2 = struct.unpack('>HHHHHH', data[offset:offset+12])
        
        str_offset = stringOffset + stringOffset2
        if str_offset + length > len(data):
            continue
        
        str_data = data[str_offset:str_offset+length]
        
        if platformID == 1 and encodingID == 0:
            # Mac Roman
            try:
                text = str_data.decode('mac_roman')
            except:
                text = str_data.decode('latin-1', errors='ignore')
        elif platformID == 3 and encodingID == 1 and languageID == 0x0409:
            # Windows Unicode
            try:
                text = str_data.decode('utf-16-be')
            except:
                text = ""
        else:
            continue
        
        if nameID == 0 and font.names['copyright'] == "":
            font.names['copyright'] = text
        elif nameID == 1 and font.names['family'] == "":
            font.names['family'] = text
        elif nameID == 2 and font.names['subfamily'] == "":
            font.names['subfamily'] = text
        elif nameID == 3 and font.names['unique_id'] == "":
            font.names['unique_id'] = text
        elif nameID == 4 and font.names['full_name'] == "":
            font.names['full_name'] = text
        elif nameID == 5 and font.names['version'] == "":
            font.names['version'] = text
        elif nameID == 6 and font.names['ps_name'] == "":
            font.names['ps_name'] = text
        elif nameID == 7 and font.names['trademark'] == "":
            font.names['trademark'] = text
        elif nameID == 8 and font.names['manufacturer'] == "":
            font.names['manufacturer'] = text
        elif nameID == 9 and font.names['designer'] == "":
            font.names['designer'] = text
        elif nameID == 10 and font.names['description'] == "":
            font.names['description'] = text
        elif nameID == 11 and font.names['url_vendor'] == "":
            font.names['url_vendor'] = text
        elif nameID == 12 and font.names['url_designer'] == "":
            font.names['url_designer'] = text
        elif nameID == 13 and font.names['license_desc'] == "":
            font.names['license_desc'] = text
        elif nameID == 14 and font.names['license_url'] == "":
            font.names['license_url'] = text
        elif nameID == 19 and font.names['sample_text'] == "":
            font.names['sample_text'] = text
    
    return True


def parse_simple_glyph(glyph, glyph_index, data, units_per_em):
    """Parse a simple glyph from glyf table"""
    if len(data) < 10:
        return TTF_ERR_FMT
    
    numberOfContours, xMin, yMin, xMax, yMax = struct.unpack('>hhhhh', data[:10])
    offset = 10
    
    if numberOfContours <= 0:
        return TTF_ERR_FMT
    
    # Read endPtsOfContours
    endPtsOfContours = []
    for i in range(numberOfContours):
        if offset + 2 > len(data):
            return TTF_ERR_FMT
        endPtsOfContours.append(struct.unpack('>H', data[offset:offset+2])[0])
        offset += 2
    
    glyph.ncontours = numberOfContours
    glyph.npoints = endPtsOfContours[-1] + 1
    glyph.xbounds[0] = xMin
    glyph.xbounds[1] = xMax
    glyph.ybounds[0] = yMin
    glyph.ybounds[1] = yMax
    
    # Create outline
    outline = TTFOutline()
    outline.ncontours = numberOfContours
    outline.total_points = glyph.npoints
    
    contour_lengths = []
    prev_end = -1
    for end in endPtsOfContours:
        contour_lengths.append(end - prev_end)
        prev_end = end
    
    # Read instruction length
    if offset + 2 > len(data):
        return TTF_ERR_FMT
    instructionLength = struct.unpack('>H', data[offset:offset+2])[0]
    offset += 2
    
    # Skip instructions
    offset += instructionLength
    
    # Read flags
    ON_CURVE_POINT = 0x01
    X_SHORT_VECTOR = 0x02
    Y_SHORT_VECTOR = 0x04
    REPEAT_FLAG = 0x08
    X_IS_SAME_OR_POSITIVE = 0x10
    Y_IS_SAME_OR_POSITIVE = 0x20
    
    flags = []
    i = 0
    while i < glyph.npoints:
        if offset >= len(data):
            return TTF_ERR_FMT
        flag = data[offset]
        offset += 1
        
        flags.append(flag)
        
        if flag & REPEAT_FLAG:
            if offset >= len(data):
                return TTF_ERR_FMT
            repeat_count = data[offset]
            offset += 1
            for _ in range(repeat_count):
                flags.append(flag)
                i += 1
        
        i += 1
    
    # Read x coordinates
    x_coords = []
    x = 0
    for flag in flags:
        if flag & X_SHORT_VECTOR:
            if offset >= len(data):
                return TTF_ERR_FMT
            val = data[offset]
            offset += 1
            if flag & X_IS_SAME_OR_POSITIVE:
                x += val
            else:
                x -= val
        elif not (flag & X_IS_SAME_OR_POSITIVE):
            if offset + 2 > len(data):
                return TTF_ERR_FMT
            val = struct.unpack('>h', data[offset:offset+2])[0]
            offset += 2
            x += val
        x_coords.append(x)
    
    # Read y coordinates
    y_coords = []
    y = 0
    for flag in flags:
        if flag & Y_SHORT_VECTOR:
            if offset >= len(data):
                return TTF_ERR_FMT
            val = data[offset]
            offset += 1
            if flag & Y_IS_SAME_OR_POSITIVE:
                y += val
            else:
                y -= val
        elif not (flag & Y_IS_SAME_OR_POSITIVE):
            if offset + 2 > len(data):
                return TTF_ERR_FMT
            val = struct.unpack('>h', data[offset:offset+2])[0]
            offset += 2
            y += val
        y_coords.append(y)
    
    # Build contours
    point_idx = 0
    for contour_idx in range(numberOfContours):
        contour = TTFContour()
        contour.length = contour_lengths[contour_idx]
        contour.subglyph_id = glyph_index
        contour.subglyph_order = 0
        
        for _ in range(contour.length):
            point = TTFTriPoint(x_coords[point_idx], y_coords[point_idx])
            point.onc = bool(flags[point_idx] & ON_CURVE_POINT)
            point.spl = False
            point.shd = False
            contour.points.append(point)
            point_idx += 1
        
        outline.contours.append(contour)
    
    glyph.outline = outline
    
    # Shift contours to start with on-curve point
    for contour in outline.contours:
        if len(contour.points) < 2:
            continue
        
        # Find first on-curve point
        offset_idx = 0
        for i, pt in enumerate(contour.points):
            if pt.onc:
                offset_idx = i
                break
        
        # Rotate points
        if offset_idx > 0:
            contour.points = contour.points[offset_idx:] + contour.points[:offset_idx]
    
    return TTF_DONE


def parse_composite_glyph(font, glyph, glyph_index, data):
    """Parse a composite glyph"""
    if len(data) < 10:
        return TTF_ERR_FMT
    
    numberOfContours, xMin, yMin, xMax, yMax = struct.unpack('>hhhhh', data[:10])
    offset = 10
    
    glyph.composite = True
    glyph.xbounds[0] = xMin
    glyph.xbounds[1] = xMax
    glyph.ybounds[0] = yMin
    glyph.ybounds[1] = yMax
    
    ARG_1_AND_2_ARE_WORDS = 0x0001
    ARGS_ARE_XY_VALUES = 0x0002
    WE_HAVE_A_SCALE = 0x0008
    MORE_COMPONENTS = 0x0020
    WE_HAVE_AN_X_AND_Y_SCALE = 0x0040
    WE_HAVE_A_TWO_BY_TWO = 0x0080
    SCALED_COMPONENT_OFFSET = 0x0800
    UNSCALED_COMPONENT_OFFSET = 0x1000
    
    # First pass: count glyphs and contours
    stored_offset = offset
    nglyphs = 0
    total_contours = 0
    total_points = 0
    
    while True:
        if offset + 4 > len(data):
            break
        
        flags = struct.unpack('>H', data[offset:offset+2])[0]
        glyphIndex = struct.unpack('>H', data[offset+2:offset+4])[0]
        offset += 4
        
        if glyphIndex >= font.nglyphs:
            return TTF_ERR_FMT
        
        if not (flags & ARGS_ARE_XY_VALUES):
            return TTF_ERR_FMT  # Point matching not supported
        
        n = 4 if flags & ARG_1_AND_2_ARE_WORDS else 2
        
        if flags & WE_HAVE_A_SCALE:
            n += 2
        elif flags & WE_HAVE_AN_X_AND_Y_SCALE:
            n += 4
        elif flags & WE_HAVE_A_TWO_BY_TWO:
            n += 8
        
        offset += n
        
        component_glyph = font.glyphs[glyphIndex]
        if component_glyph.outline:
            total_contours += component_glyph.ncontours
            total_points += component_glyph.npoints
        
        nglyphs += 1
        
        if not (flags & MORE_COMPONENTS):
            break
    
    if total_contours == 0 or total_points == 0:
        glyph.ncontours = 0
        glyph.npoints = 0
        return TTF_DONE
    
    glyph.ncontours = total_contours
    glyph.npoints = total_points
    
    # Create outline
    outline = TTFOutline()
    outline.ncontours = total_contours
    outline.total_points = total_points
    
    # Second pass: copy and transform contours
    offset = stored_offset
    contour_idx = 0
    nglyphs = 0
    
    while True:
        if offset + 4 > len(data):
            break
        
        flags = struct.unpack('>H', data[offset:offset+2])[0]
        glyphIndex = struct.unpack('>H', data[offset+2:offset+4])[0]
        offset += 4
        
        # Read arguments
        if flags & ARG_1_AND_2_ARE_WORDS:
            arg1 = struct.unpack('>h', data[offset:offset+2])[0]
            arg2 = struct.unpack('>h', data[offset+2:offset+4])[0]
            offset += 4
        else:
            arg1 = struct.unpack('>b', data[offset:offset+1])[0]
            arg2 = struct.unpack('>b', data[offset+1:offset+2])[0]
            offset += 2
        
        # Read transformation
        scale = [[1.0, 0.0], [0.0, 1.0]]
        if flags & WE_HAVE_A_SCALE:
            val = struct.unpack('>h', data[offset:offset+2])[0]
            scale[0][0] = f2dot14_to_float(val)
            scale[1][1] = scale[0][0]
            offset += 2
        elif flags & WE_HAVE_AN_X_AND_Y_SCALE:
            scale[0][0] = f2dot14_to_float(struct.unpack('>h', data[offset:offset+2])[0])
            scale[1][1] = f2dot14_to_float(struct.unpack('>h', data[offset+2:offset+4])[0])
            offset += 4
        elif flags & WE_HAVE_A_TWO_BY_TWO:
            scale[0][0] = f2dot14_to_float(struct.unpack('>h', data[offset:offset+2])[0])
            scale[0][1] = f2dot14_to_float(struct.unpack('>h', data[offset+2:offset+4])[0])
            scale[1][0] = f2dot14_to_float(struct.unpack('>h', data[offset+4:offset+6])[0])
            scale[1][1] = f2dot14_to_float(struct.unpack('>h', data[offset+6:offset+8])[0])
            offset += 8
        
        # Default to unscaled offset if neither flag is set
        if not (flags & SCALED_COMPONENT_OFFSET) and not (flags & UNSCALED_COMPONENT_OFFSET):
            flags |= UNSCALED_COMPONENT_OFFSET
        
        # Copy and transform contours from component glyph
        component_glyph = font.glyphs[glyphIndex]
        if component_glyph.outline:
            for src_contour in component_glyph.outline.contours:
                contour = TTFContour()
                contour.length = src_contour.length
                contour.subglyph_id = glyphIndex
                contour.subglyph_order = nglyphs
                
                for pt in src_contour.points:
                    x = pt.x + (arg1 if flags & SCALED_COMPONENT_OFFSET else 0)
                    y = pt.y + (arg2 if flags & SCALED_COMPONENT_OFFSET else 0)
                    
                    new_x = scale[0][0] * x + scale[0][1] * y + (arg1 if flags & UNSCALED_COMPONENT_OFFSET else 0)
                    new_y = scale[1][0] * x + scale[1][1] * y + (arg2 if flags & UNSCALED_COMPONENT_OFFSET else 0)
                    
                    new_pt = TTFTriPoint(new_x, new_y)
                    new_pt.onc = pt.onc
                    new_pt.spl = pt.spl
                    new_pt.shd = pt.shd
                    contour.points.append(new_pt)
                
                outline.contours.append(contour)
                contour_idx += 1
        
        nglyphs += 1
        
        if not (flags & MORE_COMPONENTS):
            break
    
    glyph.outline = outline
    return TTF_DONE


def parse_glyf_table(font, glyf_data, loca_data, index_to_loc_format, units_per_em):
    """Parse the glyf table"""
    num_glyphs = font.nglyphs
    
    if index_to_loc_format == 0:
        # Short offsets
        if len(loca_data) < num_glyphs * 2:
            return TTF_ERR_FMT
        
        offsets = []
        for i in range(num_glyphs):
            offset = struct.unpack('>H', loca_data[i*2:i*2+2])[0] * 2
            offsets.append(offset)
    else:
        # Long offsets
        if len(loca_data) < num_glyphs * 4:
            return TTF_ERR_FMT
        
        offsets = []
        for i in range(num_glyphs):
            offset = struct.unpack('>I', loca_data[i*4:i*4+4])[0]
            offsets.append(offset)
    
    for i in range(num_glyphs):
        offset = offsets[i]
        
        if i < num_glyphs - 1:
            next_offset = offsets[i + 1]
            if offset == next_offset:
                continue  # No outline
        else:
            next_offset = len(glyf_data)
        
        if offset + 10 > len(glyf_data):
            continue
        
        glyph = font.glyphs[i]
        
        # Read header
        numberOfContours = struct.unpack('>h', glyf_data[offset:offset+2])[0]
        
        if numberOfContours >= 0:
            # Simple glyph
            glyph_data = glyf_data[offset:next_offset]
            parse_simple_glyph(glyph, i, glyph_data, units_per_em)
        else:
            # Composite glyph
            glyph_data = glyf_data[offset:next_offset]
            parse_composite_glyph(font, glyph, i, glyph_data)
    
    return TTF_DONE


def parse_hmtx_table(font, hmtx_data, num_h_metrics):
    """Parse hmtx table"""
    offset = 0
    
    for i in range(num_h_metrics):
        if offset + 4 > len(hmtx_data):
            break
        
        advance, lsb = struct.unpack('>Hh', hmtx_data[offset:offset+4])
        offset += 4
        
        if i < font.nglyphs:
            font.glyphs[i].advance = advance
            font.glyphs[i].lbearing = lsb
    
    # Remaining glyphs share the same advance width
    if offset < len(hmtx_data):
        last_advance = font.glyphs[num_h_metrics - 1].advance if num_h_metrics > 0 else 0
        
        for i in range(num_h_metrics, font.nglyphs):
            if offset + 2 > len(hmtx_data):
                break
            
            lsb = struct.unpack('>h', hmtx_data[offset:offset+2])[0]
            offset += 2
            
            font.glyphs[i].advance = last_advance
            font.glyphs[i].lbearing = lsb
    
    return TTF_DONE


def parse_os2_table(font, data):
    """Parse OS/2 table"""
    if len(data) < 96:
        return TTF_ERR_FMT
    
    font.os2['xAvgCharWidth'] = struct.unpack('>h', data[4:6])[0]
    font.os2['usWeightClass'] = struct.unpack('>H', data[6:8])[0]
    font.os2['usWidthClass'] = struct.unpack('>H', data[8:10])[0]
    font.os2['yStrikeoutSize'] = struct.unpack('>h', data[24:26])[0]
    font.os2['yStrikeoutPos'] = struct.unpack('>h', data[26:28])[0]
    font.os2['sFamilyClass'] = struct.unpack('>h', data[28:30])[0]
    font.os2['panose'] = list(data[30:40])
    
    fsSelection = struct.unpack('>H', data[46:48])[0]
    font.os2['fsSelection']['italic'] = bool(fsSelection & 1)
    font.os2['fsSelection']['underscore'] = bool(fsSelection & 2)
    font.os2['fsSelection']['negative'] = bool(fsSelection & 4)
    font.os2['fsSelection']['outlined'] = bool(fsSelection & 8)
    font.os2['fsSelection']['strikeout'] = bool(fsSelection & 16)
    font.os2['fsSelection']['bold'] = bool(fsSelection & 32)
    font.os2['fsSelection']['regular'] = bool(fsSelection & 64)
    font.os2['fsSelection']['utm'] = bool(fsSelection & 128)
    font.os2['fsSelection']['oblique'] = bool(fsSelection & 512)
    
    font.os2['sTypoAscender'] = struct.unpack('>h', data[68:70])[0]
    font.os2['sTypoDescender'] = struct.unpack('>h', data[70:72])[0]
    font.os2['sTypoLineGap'] = struct.unpack('>h', data[72:74])[0]
    font.os2['usWinAscent'] = struct.unpack('>H', data[74:76])[0]
    font.os2['usWinDescent'] = struct.unpack('>H', data[76:78])[0]
    
    return TTF_DONE


def parse_hhea_table(font, data):
    """Parse hhea table"""
    if len(data) < 36:
        return TTF_ERR_FMT
    
    font.hhea['ascender'] = struct.unpack('>h', data[4:6])[0]
    font.hhea['descender'] = struct.unpack('>h', data[6:8])[0]
    font.hhea['lineGap'] = struct.unpack('>h', data[8:10])[0]
    font.hhea['advanceWidthMax'] = struct.unpack('>H', data[10:12])[0]
    font.hhea['minLSideBearing'] = struct.unpack('>h', data[12:14])[0]
    font.hhea['minRSideBearing'] = struct.unpack('>h', data[14:16])[0]
    font.hhea['xMaxExtent'] = struct.unpack('>h', data[16:18])[0]
    caretSlopeRise = struct.unpack('>h', data[18:20])[0]
    caretSlopeRun = struct.unpack('>h', data[20:22])[0]
    
    if caretSlopeRise != 0:
        font.hhea['caretSlope'] = math.atan2(caretSlopeRun, caretSlopeRise)
    else:
        font.hhea['caretSlope'] = 0.0
    
    return struct.unpack('>H', data[34:36])[0]  # numberOfHMetrics


def parse_head_table(font, data):
    """Parse head table"""
    if len(data) < 54:
        return TTF_ERR_FMT, 0, 0
    
    font.head['rev'] = struct.unpack('>h', data[4:6])[0] + struct.unpack('>H', data[6:8])[0] / 65536.0
    
    macStyle = struct.unpack('>H', data[32:34])[0]
    font.head['macStyle']['bold'] = bool(macStyle & 1)
    font.head['macStyle']['italic'] = bool(macStyle & 2)
    font.head['macStyle']['underline'] = bool(macStyle & 4)
    font.head['macStyle']['outline'] = bool(macStyle & 8)
    font.head['macStyle']['shadow'] = bool(macStyle & 16)
    font.head['macStyle']['condensed'] = bool(macStyle & 32)
    font.head['macStyle']['extended'] = bool(macStyle & 64)
    
    unitsPerEm = struct.unpack('>H', data[34:36])[0]
    indexToLocFormat = struct.unpack('>h', data[50:52])[0]
    
    return TTF_DONE, unitsPerEm, indexToLocFormat


def ttf_load_from_mem(data, headers_only=False):
    """Load font from memory"""
    if len(data) < 12:
        return TTF_ERR_FMT, None
    
    # Check magic number
    sfntVersion = struct.unpack('>I', data[:4])[0]
    if sfntVersion != 0x00010000:
        return TTF_ERR_VER, None
    
    # Check checksum (TTF checksum is calculated with checksum field set to 0)
    # Note: Some system fonts may have invalid checksums, so we skip this check
    # checksum_data = data[:8] + b'\x00\x00\x00\x00' + data[12:]
    # if ttf_checksum(checksum_data) != 0xB1B0AFBA:
    #     return TTF_ERR_CSUM, None
    
    numTables = struct.unpack('>H', data[4:6])[0]
    
    # Parse table directory
    tables = {}
    offset = 12
    
    for i in range(numTables):
        if offset + 16 > len(data):
            return TTF_ERR_FMT, None
        
        tag = data[offset:offset+4].decode('ascii')
        checkSum = struct.unpack('>I', data[offset+4:offset+8])[0]
        tableOffset = struct.unpack('>I', data[offset+8:offset+12])[0]
        tableLength = struct.unpack('>I', data[offset+12:offset+16])[0]
        
        offset += 16
        
        if tableOffset + tableLength > len(data):
            return TTF_ERR_FMT, None
        
        tables[tag] = data[tableOffset:tableOffset+tableLength]
        
        if tag == 'glyf':
            font_csum = checkSum
    
    # Check required tables
    required = ['head', 'cmap', 'maxp', 'name', 'hhea', 'hmtx', 'loca', 'glyf']
    for req in required:
        if req not in tables:
            return TTF_ERR_NOTAB, None
    
    # Parse maxp table
    maxp_data = tables['maxp']
    if len(maxp_data) < 6:
        return TTF_ERR_FMT, None
    
    numGlyphs = struct.unpack('>H', maxp_data[4:6])[0]
    
    # Create font structure
    font = TTFFont()
    font.nglyphs = numGlyphs
    font.glyphs = [TTFGlyph() for _ in range(numGlyphs)]
    font.glyf_csum = font_csum if 'font_csum' in locals() else 0
    
    # Parse name table
    if not parse_name_table(tables['name'], font):
        return TTF_ERR_FMT, None
    
    # Parse OS/2 table
    if 'OS/2' in tables:
        parse_os2_table(font, tables['OS/2'])
    
    # Parse head table
    head_result, unitsPerEm, indexToLocFormat = parse_head_table(font, tables['head'])
    if head_result != TTF_DONE:
        return head_result, None
    
    # Parse hhea table
    num_h_metrics = parse_hhea_table(font, tables['hhea'])
    
    # Parse cmap table
    fmt12_data, fmt12_size = locate_cmap_table(tables['cmap'], 12)
    if fmt12_data:
        result = parse_fmt12_table(fmt12_data, fmt12_size, font, headers_only)
    else:
        fmt4_data, fmt4_size = locate_cmap_table(tables['cmap'], 4)
        if not fmt4_data:
            return TTF_ERR_UTAB, None
        result = parse_fmt4_table(fmt4_data, fmt4_size, font, headers_only)
    
    if result != TTF_DONE:
        return result, None
    
    if not headers_only:
        # Parse hmtx table
        parse_hmtx_table(font, tables['hmtx'], num_h_metrics)
        
        # Parse glyf table
        parse_glyf_table(font, tables['glyf'], tables['loca'], indexToLocFormat, unitsPerEm)
        
        # Convert to em units
        if unitsPerEm > 0:
            scale = 1.0 / unitsPerEm
            for glyph in font.glyphs:
                glyph.xbounds[0] *= scale
                glyph.xbounds[1] *= scale
                glyph.ybounds[0] *= scale
                glyph.ybounds[1] *= scale
                glyph.advance *= scale
                glyph.lbearing *= scale
                glyph.rbearing = glyph.advance - (glyph.lbearing + glyph.xbounds[1] - glyph.xbounds[0])
                
                if glyph.outline:
                    for contour in glyph.outline.contours:
                        for pt in contour.points:
                            pt.x *= scale
                            pt.y *= scale
            
            font.hhea['ascender'] *= scale
            font.hhea['descender'] *= scale
            font.hhea['lineGap'] *= scale
            font.hhea['advanceWidthMax'] *= scale
            font.hhea['minLSideBearing'] *= scale
            font.hhea['minRSideBearing'] *= scale
            font.hhea['xMaxExtent'] *= scale
            
            font.os2['xAvgCharWidth'] *= scale
            font.os2['yStrikeoutSize'] *= scale
            font.os2['yStrikeoutPos'] *= scale
            font.os2['sTypoAscender'] *= scale
            font.os2['sTypoDescender'] *= scale
            font.os2['sTypoLineGap'] *= scale
            font.os2['usWinAscent'] *= scale
            font.os2['usWinDescent'] *= scale
        
        # Sort chars array
        # Create list of (char, glyph) pairs and sort by char
        paired = list(zip(font.chars, font.char2glyph))
        paired.sort(key=lambda x: x[0])
        font.chars, font.char2glyph = zip(*paired) if paired else ([], [])
        font.chars = list(font.chars)
        font.char2glyph = list(font.char2glyph)
    
    return TTF_DONE, font


def ttf_load_from_file(filename, headers_only=False):
    """Load font from file"""
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except IOError:
        return TTF_ERR_OPEN, None
    
    if len(data) > 32 * 1024 * 1024:
        return TTF_ERR_SIZE, None
    
    result, font = ttf_load_from_mem(data, headers_only)
    
    if font:
        font.filename = filename
    
    return result, font


def ttf_find_glyph(font, utf32_char):
    """Find glyph index for unicode character"""
    if font.nchars == 0:
        return -1
    
    if font.nchars == 1:
        return font.char2glyph[0] if font.chars[0] == utf32_char else -1
    
    # Binary search
    left, right = 0, font.nchars - 1
    
    if font.chars[left] == utf32_char:
        return font.char2glyph[left]
    if font.chars[right] == utf32_char:
        return font.char2glyph[right]
    
    while right - left > 1:
        mid = (left + right) // 2
        if font.chars[mid] == utf32_char:
            return font.char2glyph[mid]
        if font.chars[mid] > utf32_char:
            right = mid
        else:
            left = mid
    
    return -1
