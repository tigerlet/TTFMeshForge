import math
from .core import *


def qbezier(p0, p1, p2, t):
    """Calculate point on quadratic bezier curve"""
    tt = 1.0 - t
    return tt * tt * p0 + 2.0 * t * tt * p1 + t * t * p2


def qbezier_diff1(p0, p1, p2, t):
    """First derivative of bezier curve"""
    return 2.0 * (t * (p0 - 2.0 * p1 + p2) - p0 + p1)


def linearize_qbezier(curve, quality):
    """Linearize a single quadratic bezier curve"""
    v1 = [
        qbezier_diff1(curve[0].x, curve[1].x, curve[2].x, 0.0),
        qbezier_diff1(curve[0].y, curve[1].y, curve[2].y, 0.0)
    ]
    v2 = [
        qbezier_diff1(curve[0].x, curve[1].x, curve[2].x, 1.0),
        qbezier_diff1(curve[0].y, curve[1].y, curve[2].y, 1.0)
    ]
    
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    if abs(cross) < EPSILON:
        return []
    
    len1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    len2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    
    if len1 < EPSILON or len2 < EPSILON:
        return []
    
    angle = abs(cross) / (len1 * len2)
    if angle >= 1.0:
        angle = 1.0
    angle = math.asin(angle)
    
    num_points = int(round(angle / (math.pi * 2) * quality))
    if num_points == 0:
        return []
    
    step = 1.0 / (num_points + 1)
    points = []
    
    for i in range(num_points):
        t = step * (i + 1)
        x = qbezier(curve[0].x, curve[1].x, curve[2].x, t)
        y = qbezier(curve[0].y, curve[1].y, curve[2].y, t)
        points.append(TTFTriPoint(x, y))
    
    return points


def herons_area_p(a, b, c):
    """Calculate area of triangle formed by three points"""
    dx1 = b.x - a.x
    dy1 = b.y - a.y
    dx2 = c.x - a.x
    dy2 = c.y - a.y
    return abs(dx1 * dy2 - dx2 * dy1) / 2.0


def linearize_contour(src_points, quality):
    """Linearize a contour with bezier curves"""
    if len(src_points) < 2:
        return []
    
    result = []
    state = 0
    queue = [None, None, None]
    
    for i, pt in enumerate(src_points):
        if state == 0:
            queue[0] = pt
            result.append(TTFTriPoint(pt.x, pt.y))
            result[-1].onc = pt.onc
            state = 1
        
        elif state == 1:
            if pt.onc:
                result.append(TTFTriPoint(pt.x, pt.y))
                result[-1].onc = True
                queue[0] = pt
            else:
                queue[1] = pt
                state = 2
        
        elif state == 2:
            if pt.onc:
                queue[2] = pt
                
                if herons_area_p(queue[0], queue[1], queue[2]) > 1e-5:
                    bezier_points = linearize_qbezier(queue, quality)
                    result.extend(bezier_points)
                
                result.append(TTFTriPoint(pt.x, pt.y))
                result[-1].onc = True
                queue[0] = pt
                state = 1
            else:
                mid_x = (queue[1].x + pt.x) / 2.0
                mid_y = (queue[1].y + pt.y) / 2.0
                queue[2] = TTFTriPoint(mid_x, mid_y)
                queue[2].onc = True
                queue[2].spl = True
                
                if herons_area_p(queue[0], queue[1], queue[2]) > 1e-5:
                    bezier_points = linearize_qbezier(queue, quality)
                    result.extend(bezier_points)
                
                result.append(TTFTriPoint(queue[2].x, queue[2].y))
                result[-1].onc = True
                result[-1].spl = True
                
                queue[0] = queue[2]
                queue[1] = pt
    
    if state == 2 and len(src_points) > 0:
        queue[2] = TTFTriPoint(src_points[0].x, src_points[0].y)
        queue[2].onc = src_points[0].onc
        
        if herons_area_p(queue[0], queue[1], queue[2]) > 1e-5:
            bezier_points = linearize_qbezier(queue, quality)
            result.extend(bezier_points)
    
    return result


def fix_linear_bags(points):
    """Remove collinear points"""
    if len(points) < 3:
        return points
    
    result = [points[0]]
    
    for i in range(1, len(points) - 1):
        if herons_area_p(result[-1], points[i], points[i+1]) > EPSILON:
            result.append(points[i])
    
    result.append(points[-1])
    
    while len(result) > 1:
        dx = result[0].x - result[-1].x
        dy = result[0].y - result[-1].y
        if abs(dx) > EPSILON or abs(dy) > EPSILON:
            break
        result.pop()
    
    return result if len(result) >= 3 else []


def fill_shading_flags(points):
    """Set smooth shading flags"""
    if len(points) < 3:
        return
    
    for i in range(len(points)):
        p_prev = points[(i - 1) % len(points)]
        p_curr = points[i]
        p_next = points[(i + 1) % len(points)]
        
        if p_curr.onc:
            p_curr.shd = not p_prev.onc and not p_next.onc
        else:
            p_curr.shd = True


def ttf_linear_outline(glyph, quality=TTF_QUALITY_NORMAL):
    """Create linearized outline from glyph"""
    if glyph.outline is None:
        return None
    
    outline = TTFOutline()
    
    total_points = 0
    
    for src_contour in glyph.outline.contours:
        contour = TTFContour()
        contour.subglyph_id = src_contour.subglyph_id
        contour.subglyph_order = src_contour.subglyph_order
        
        points = linearize_contour(src_contour.points, quality)
        points = fix_linear_bags(points)
        
        if len(points) < 3:
            continue
        
        fill_shading_flags(points)
        
        contour.points = points
        contour.length = len(points)
        total_points += len(points)
        
        outline.contours.append(contour)
    
    outline.ncontours = len(outline.contours)
    outline.total_points = total_points
    
    return outline


def ttf_splitted_outline(glyph):
    """Create splitted outline from glyph"""
    if glyph.outline is None:
        return None
    
    outline = TTFOutline()
    
    total_points = 0
    
    for src_contour in glyph.outline.contours:
        contour = TTFContour()
        contour.subglyph_id = src_contour.subglyph_id
        contour.subglyph_order = src_contour.subglyph_order
        
        points = []
        state = 0
        
        for pt in src_contour.points:
            if state == 0:
                points.append(TTFTriPoint(pt.x, pt.y))
                points[-1].onc = pt.onc
                state = 1
            elif state == 1:
                points.append(TTFTriPoint(pt.x, pt.y))
                points[-1].onc = pt.onc
                state = 1 if pt.onc else 2
            elif state == 2:
                if pt.onc:
                    points.append(TTFTriPoint(pt.x, pt.y))
                    points[-1].onc = True
                    state = 1
                else:
                    mid_x = (points[-1].x + pt.x) / 2.0
                    mid_y = (points[-1].y + pt.y) / 2.0
                    mid_pt = TTFTriPoint(mid_x, mid_y)
                    mid_pt.onc = True
                    mid_pt.spl = True
                    points.append(mid_pt)
                    points.append(TTFTriPoint(pt.x, pt.y))
                    points[-1].onc = False
        
        contour.points = points
        contour.length = len(points)
        total_points += len(points)
        
        outline.contours.append(contour)
    
    outline.ncontours = len(outline.contours)
    outline.total_points = total_points
    
    return outline


def ttf_outline_evenodd_base(outline, point, contour_idx):
    """Base even-odd algorithm for single contour"""
    counter = 0
    
    contour = outline.contours[contour_idx]
    points = contour.points
    n = len(points)
    
    for i in range(n):
        x1, y1 = points[i].x, points[i].y
        x2, y2 = points[(i + 1) % n].x, points[(i + 1) % n].y
        
        # Check if the edge crosses the horizontal line going right from the point
        # Edge goes from (x1,y1) to (x2,y2)
        if ((y1 > point[1]) != (y2 > point[1])):
            # Edge crosses the horizontal line
            # Calculate intersection x coordinate
            t = (point[1] - y1) / (y2 - y1) if (y2 - y1) != 0 else 0.0
            x_intersect = x1 + t * (x2 - x1)
            
            # If intersection is to the right of the point, increment counter
            if point[0] < x_intersect:
                counter += 1
    
    return counter


def ttf_outline_evenodd(outline, point, subglyph_order=-1):
    """Even-odd algorithm for point in outline"""
    count = 0
    for i, contour in enumerate(outline.contours):
        if subglyph_order >= 0 and contour.subglyph_order != subglyph_order:
            continue
        count += ttf_outline_evenodd_base(outline, point, i)
    
    return (count & 1) == 1


def ttf_outline_contour_info(outline, subglyph_order, contour_idx):
    """Determine if contour is a hole and find nesting"""
    test_point = outline.contours[contour_idx].points[0]
    point = [test_point.x, test_point.y]
    
    count = 0
    nested_to = -1
    
    for i, contour in enumerate(outline.contours):
        if i == contour_idx:
            continue
        if subglyph_order >= 0 and contour.subglyph_order != subglyph_order:
            continue
        
        res = ttf_outline_evenodd_base(outline, point, i)
        count += res
        
        if (res & 1) == 1:
            if nested_to == -1:
                nested_to = i
    
    is_hole = (count & 1) == 1
    return is_hole, nested_to


def ttf_glyph2svgpath(glyph, xscale=1.0, yscale=1.0):
    """Convert glyph to SVG path string"""
    outline = ttf_splitted_outline(glyph)
    if outline is None:
        return None
    
    path_parts = []
    
    for contour in outline.contours:
        if len(contour.points) < 2:
            continue
        
        points = contour.points
        path_parts.append(f'M {points[0].x * xscale:.3f} {points[0].y * yscale:.3f}')
        
        j = 0
        while j < len(points):
            if j == len(points) - 1:
                break
            
            if points[j + 1].onc:
                j += 1
                path_parts.append(f'L {points[j].x * xscale:.3f} {points[j].y * yscale:.3f}')
            else:
                if j + 2 < len(points):
                    path_parts.append(f'Q {points[j+1].x * xscale:.3f} {points[j+1].y * yscale:.3f} {points[j+2].x * xscale:.3f} {points[j+2].y * yscale:.3f}')
                    j += 2
        
        path_parts.append('Z')
    
    return ' '.join(path_parts)


def ttf_glyph_to_svg(glyph, width=512, height=512, margin=20):
    """Convert glyph to SVG string"""
    outline = ttf_splitted_outline(glyph)
    if outline is None:
        return None
    
    all_points = []
    for contour in outline.contours:
        all_points.extend(contour.points)
    
    if not all_points:
        return None
    
    min_x = min(p.x for p in all_points)
    max_x = max(p.x for p in all_points)
    min_y = min(p.y for p in all_points)
    max_y = max(p.y for p in all_points)
    
    glyph_width = max_x - min_x
    glyph_height = max_y - min_y
    
    if glyph_width < EPSILON or glyph_height < EPSILON:
        return None
    
    scale = min((width - margin * 2) / glyph_width, (height - margin * 2) / glyph_height)
    
    offset_x = margin - min_x * scale
    offset_y = height - margin + min_y * scale
    
    path_str = ttf_glyph2svgpath(glyph, scale, -scale)
    
    svg_parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        '<path fill="black" d="',
        path_str,
        f'" transform="translate({offset_x},{offset_y})"/>',
        '</svg>'
    ]
    
    return ''.join(svg_parts)
