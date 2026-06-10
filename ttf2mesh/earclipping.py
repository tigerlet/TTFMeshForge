"""
Polygon triangulation module for Chinese font glyphs
Implements: Hierarchical nesting -> Boundary normalization -> CDT core -> Post-processing

Algorithm:
1. Preprocessing: Bezier→polyline, direction normalization (CCW outer, CW inner)
2. Nesting tree construction: identify which holes belong to which contours
3. Hole merging (bridge cutting): merge holes into outer contour using cutting bridges
4. Constrained Delaunay triangulation via scipy
5. Recursive handling of multi-layer nesting
6. Post-processing: quality filtering, redundancy cleanup
"""

import math
import numpy as np

EPSILON = 1e-10


# ============================================================================
# Geometry utilities
# ============================================================================

def polygon_signed_area(vertices):
    """Calculate signed area. Positive=CW, Negative=CCW"""
    area = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area += (x1 * y2) - (x2 * y1)
    return area / 2.0


def is_ccw(vertices):
    """Check if polygon is counter-clockwise (CCW)"""
    return polygon_signed_area(vertices) < 0


def point_in_polygon(x, y, polygon):
    """Ray casting algorithm for point-in-polygon test"""
    inside = False
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)):
            if yj == yi:
                continue
            x_intersect = (y - yi) * (xj - xi) / (yj - yi) + xi
            if x < x_intersect:
                inside = not inside
    return inside


def centroid_of_polygon(vertices):
    """Calculate centroid of polygon"""
    cx = sum(v[0] for v in vertices) / len(vertices)
    cy = sum(v[1] for v in vertices) / len(vertices)
    return (cx, cy)


def contour_contains(inner, outer):
    """
    Check if inner contour is fully inside outer contour.
    Uses bounding box test + centroid test for robustness.
    """
    if len(inner) < 3 or len(outer) < 3:
        return False
    
    # First check: bounding box containment (quick rejection)
    inner_xs = [v[0] for v in inner]
    inner_ys = [v[1] for v in inner]
    outer_xs = [v[0] for v in outer]
    outer_ys = [v[1] for v in outer]
    
    inner_min_x, inner_max_x = min(inner_xs), max(inner_xs)
    inner_min_y, inner_max_y = min(inner_ys), max(inner_ys)
    outer_min_x, outer_max_x = min(outer_xs), max(outer_xs)
    outer_min_y, outer_max_y = min(outer_ys), max(outer_ys)
    
    # If inner's bounding box is not fully inside outer's bounding box, it's not contained
    if inner_min_x < outer_min_x - EPSILON or inner_max_x > outer_max_x + EPSILON:
        return False
    if inner_min_y < outer_min_y - EPSILON or inner_max_y > outer_max_y + EPSILON:
        return False
    
    # Second check: centroid containment (more precise)
    cx, cy = centroid_of_polygon(inner)
    return point_in_polygon(cx, cy, outer)


def ensure_closed(points, tolerance=EPSILON):
    """Ensure contour is closed (first == last)"""
    if len(points) < 2:
        return list(points)
    first = points[0]
    last = points[-1]
    dist = math.sqrt((first[0] - last[0]) ** 2 + (first[1] - last[1]) ** 2)
    if dist > tolerance:
        return list(points) + [first]
    return list(points)


def reverse_contour(vertices):
    """Reverse vertex order (keep first, reverse rest)"""
    if len(vertices) < 2:
        return list(vertices)
    return [vertices[0]] + list(reversed(vertices[1:-1]))


def normalize_direction(vertices, force_ccw=True):
    """Ensure contour has correct winding direction"""
    if force_ccw:
        return vertices if is_ccw(vertices) else reverse_contour(vertices)
    else:
        return vertices if not is_ccw(vertices) else reverse_contour(vertices)


# ============================================================================
# Nesting tree construction
# ============================================================================

class NestingNode:
    """Node in the nesting tree"""
    def __init__(self, vertices, contour_type='outer', index=0):
        self.vertices = vertices
        self.contour_type = contour_type  # 'outer' (CCW, fill) or 'hole' (CW, empty)
        self.index = index
        self.children = []  # child nodes (holes or nested outers)

    def add_child(self, child):
        self.children.append(child)


def build_nesting_tree(contours):
    """
    Build a nesting tree from sorted contours (largest area first).
    TrueType rule: CCW=outer(fill), CW=hole(empty)
    Nesting alternates: outer(0) -> hole(1) -> outer(2) -> hole(3) ...
    """
    if not contours:
        return []

    roots = []
    # Each entry: (vertices, is_ccw, original_index)
    contour_data = [(c['points'], c['is_ccw'], c.get('index', 0)) for c in contours]

    for i, (vertices, is_outer, idx) in enumerate(contour_data):
        node = NestingNode(vertices, 'outer' if is_outer else 'hole', idx)

        # Find the deepest parent that contains this contour
        best_parent = None
        best_depth = -1

        # Try to attach to existing nodes
        def find_parent(root, depth=0):
            nonlocal best_parent, best_depth
            if root is None:
                return
            # A contour can be a child if:
            # 1. This contour is inside root's contour
            # 2. Root's depth allows this type (alternating)
            if contour_contains(vertices, root.vertices):
                if depth > best_depth:
                    best_parent = root
                    best_depth = depth
                # Try children for even deeper nesting
                for child in root.children:
                    find_parent(child, depth + 1)

        for root in roots:
            find_parent(root)

        if best_parent is not None:
            best_parent.add_child(node)
        else:
            roots.append(node)

    return roots


# ============================================================================
# Bridge cutting: merge holes into outer contour
# ============================================================================

def find_closest_points(polygon_a, polygon_b):
    """Find closest pair of points between two polygons"""
    min_dist = float('inf')
    best_a = 0
    best_b = 0
    for i, pa in enumerate(polygon_a):
        for j, pb in enumerate(polygon_b):
            d = (pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2
            if d < min_dist:
                min_dist = d
                best_a = i
                best_b = j
    return best_a, best_b


def merge_polygon_with_hole(outer, hole):
    """
    Merge a hole into outer polygon using bridge cutting.
    Creates a single simple polygon by:
    1. Find closest points between outer and hole
    2. Cut bridge from outer to hole and back
    3. Merge into single polygon
    """
    # Find closest points
    outer_idx, hole_idx = find_closest_points(outer, hole)

    # Build merged polygon:
    # - Start from outer_idx in outer, traverse to end
    # - Jump to hole via bridge
    # - Traverse hole (reversed to maintain orientation)
    # - Jump back to outer via bridge (reversed)
    # - Continue outer from start to outer_idx

    n_outer = len(outer)
    n_hole = len(hole)

    merged = []

    # Part 1: outer from outer_idx to end
    for i in range(outer_idx, n_outer):
        merged.append(outer[i])

    # Bridge: outer[outer_idx] -> hole[hole_idx]
    merged.append(hole[hole_idx])

    # Part 2: hole (traverse full hole starting from hole_idx, reversed)
    for i in range(n_hole):
        idx = (hole_idx - i) % n_hole
        if idx == hole_idx and i > 0:
            continue
        merged.append(hole[idx])

    # Bridge back: hole[hole_idx] -> outer[outer_idx]
    merged.append(outer[outer_idx])

    # Part 3: outer from start to outer_idx
    for i in range(0, outer_idx + 1):
        merged.append(outer[i])

    return merged


def merge_all_holes(outer_vertices, holes):
    """
    Merge all holes into outer polygon using sequential bridge cutting.
    Returns a single simple polygon with no holes.
    """
    result = list(outer_vertices)

    for hole in holes:
        if len(hole) < 3:
            continue
        result = merge_polygon_with_hole(result, hole)

    return result


# ============================================================================
# Core triangulation: Constrained Delaunay via centroid filtering
# ============================================================================

def segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
    """Check if two line segments intersect"""
    def ccw(A, B, C):
        return (B[0]-A[0])*(C[1]-A[1]) - (B[1]-A[1])*(C[0]-A[0])
    
    A, B, C, D = (x1, y1), (x2, y2), (x3, y3), (x4, y4)
    return (ccw(A,C,D)*ccw(B,C,D) < 0) and (ccw(A,B,C)*ccw(A,B,D) < 0)


def polygon_is_self_intersecting(vertices):
    """Check if polygon has self-intersections"""
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i+1)%n]
        # Check against all other segments except immediate neighbors
        for j in range(n):
            # Skip if same segment or adjacent segments
            if j == i or j == (i+1)%n or j == (i-1)%n:
                continue
            if (j+1)%n == i or (j+1)%n == (i+1)%n or (j+1)%n == (i-1)%n:
                continue
            x3, y3 = vertices[j]
            x4, y4 = vertices[(j+1)%n]
            if segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
                return True
    return False


def triangulate_self_intersecting_polygon(vertices):
    """
    Triangulate a self-intersecting polygon (like Chinese character '十').
    Uses a grid-based filling approach.
    """
    if len(vertices) < 3:
        return (list(vertices), [])

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y
    max_dim = max(width, height)

    if max_dim < EPSILON:
        return (list(vertices), [])

    # Use fine grid for self-intersecting polygons
    grid_steps = 50
    cell_size = max_dim / grid_steps

    # Collect all grid points inside the polygon
    grid_points = []
    for i in range(grid_steps + 1):
        for j in range(grid_steps + 1):
            x = min_x + width * i / grid_steps
            y = min_y + height * j / grid_steps
            if point_in_polygon(x, y, vertices):
                grid_points.append((x, y))

    if not grid_points:
        return (list(vertices), [])

    # Add original vertices to grid points
    all_points = list(vertices)
    vertex_set = set()
    for v in vertices:
        vertex_set.add((round(v[0] / cell_size, 0), round(v[1] / cell_size, 0)))

    for gp in grid_points:
        grid_key = (round(gp[0] / cell_size, 0), round(gp[1] / cell_size, 0))
        if grid_key not in vertex_set:
            all_points.append(gp)

    # Delaunay triangulation
    try:
        from scipy.spatial import Delaunay
        points = np.array(all_points)
        tri = Delaunay(points)

        triangles = []
        for simplex in tri.simplices:
            p0 = points[simplex[0]]
            p1 = points[simplex[1]]
            p2 = points[simplex[2]]

            cx = (p0[0] + p1[0] + p2[0]) / 3
            cy = (p0[1] + p1[1] + p2[1]) / 3

            if point_in_polygon(cx, cy, vertices):
                triangles.append(tuple(int(i) for i in simplex))

        return (all_points, triangles)
    except ImportError:
        return (list(vertices), [])


def is_linear_shape(vertices):
    """
    Detect if the polygon represents a linear/stroke shape (like '十', '一', '|').
    These shapes have small relative area compared to their bounding box.
    Uses ratio of polygon area to bounding box area.
    """
    area = abs(polygon_signed_area(vertices))
    
    # Get bounding box
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    bbox_area = width * height
    
    if bbox_area < EPSILON:
        return False
    
    # Calculate ratio of polygon area to bounding box area
    # Linear shapes like '十' have low ratio (< 0.3)
    # Solid shapes like '口' have high ratio (> 0.5)
    ratio = area / bbox_area
    
    # If ratio is very low, it's likely a linear/stroke shape
    if ratio < 0.3:
        return True
    
    return False


def triangulate_linear_shape(vertices):
    """
    Triangulate a linear/stroke shape (like '十', '一', '|').
    Uses a grid-based filling approach to fill the stroke area.
    """
    if len(vertices) < 3:
        return (list(vertices), [])

    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y
    max_dim = max(width, height)

    if max_dim < EPSILON:
        return (list(vertices), [])

    # Use dense grid for linear shapes
    grid_steps = 40
    cell_size = max_dim / grid_steps

    # Collect all grid points inside or near the polygon
    grid_points = []
    for i in range(grid_steps + 1):
        for j in range(grid_steps + 1):
            x = min_x + width * i / grid_steps
            y = min_y + height * j / grid_steps
            if point_in_polygon(x, y, vertices):
                grid_points.append((x, y))

    if not grid_points:
        # Fallback: if no points inside, use a wider margin
        for i in range(grid_steps + 1):
            for j in range(grid_steps + 1):
                x = min_x + width * i / grid_steps
                y = min_y + height * j / grid_steps
                # Check if near any vertex
                is_near = False
                for v in vertices:
                    dist = math.sqrt((x - v[0])**2 + (y - v[1])**2)
                    if dist < cell_size:
                        is_near = True
                        break
                if is_near:
                    grid_points.append((x, y))

    if not grid_points:
        return (list(vertices), [])

    # Combine original vertices with grid points
    all_points = list(vertices)
    vertex_set = set()
    for v in vertices:
        vertex_set.add((round(v[0] / cell_size, 0), round(v[1] / cell_size, 0)))

    for gp in grid_points:
        grid_key = (round(gp[0] / cell_size, 0), round(gp[1] / cell_size, 0))
        if grid_key not in vertex_set:
            all_points.append(gp)

    # Delaunay triangulation
    try:
        from scipy.spatial import Delaunay
        points = np.array(all_points)
        tri = Delaunay(points)

        triangles = []
        for simplex in tri.simplices:
            p0 = points[simplex[0]]
            p1 = points[simplex[1]]
            p2 = points[simplex[2]]

            cx = (p0[0] + p1[0] + p2[0]) / 3
            cy = (p0[1] + p1[1] + p2[1]) / 3

            # For linear shapes, accept triangles that are near the polygon
            if point_in_polygon(cx, cy, vertices):
                triangles.append(tuple(int(i) for i in simplex))
            else:
                # Also accept triangles that are close to vertices
                is_near = False
                for idx in simplex:
                    if idx < len(vertices):
                        is_near = True
                        break
                if is_near:
                    # Check if this triangle is within bounding box margin
                    margin = cell_size * 2
                    if (min_x - margin <= cx <= max_x + margin and
                        min_y - margin <= cy <= max_y + margin):
                        triangles.append(tuple(int(i) for i in simplex))

        return (all_points, triangles)
    except ImportError:
        return (list(vertices), [])


def triangulate_simple_polygon(vertices):
    """
    Triangulate a simple polygon (no holes) using scipy Delaunay + centroid filtering.
    This is the core constrained Delaunay approach.
    Handles:
    - Self-intersecting polygons (like '十') using grid-based filling
    - Linear/stroke shapes (like '十', '一') using special filling
    """
    if len(vertices) < 3:
        return (list(vertices), [])

    # Check for linear shapes (very small area but large bounding box)
    if is_linear_shape(vertices):
        return triangulate_linear_shape(vertices)

    # Check for self-intersections
    if polygon_is_self_intersecting(vertices):
        return triangulate_self_intersecting_polygon(vertices)

    try:
        from scipy.spatial import Delaunay

        # Build point set: contour vertices + interior sampling points
        all_vertices = list(vertices)
        contour_count = len(vertices)

        # Add sampling points inside the polygon for better triangulation
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y
        max_dim = max(width, height)

        if max_dim < EPSILON:
            return (all_vertices, [])

        # Adaptive grid density
        n_pts = len(vertices)
        grid_steps = max(8, min(30, int(math.sqrt(n_pts) * 2.5)))

        sample_points = []
        for i in range(1, grid_steps):
            for j in range(1, grid_steps):
                x = min_x + (max_x - min_x) * i / grid_steps
                y = min_y + (max_y - min_y) * j / grid_steps
                if point_in_polygon(x, y, vertices):
                    sample_points.append((x, y))

        # Limit samples
        if len(sample_points) > 1500:
            import random
            random.seed(42)
            sample_points = random.sample(sample_points, 1500)

        all_vertices.extend(sample_points)

        # Delaunay triangulation
        points = np.array(all_vertices)
        tri = Delaunay(points)

        # Filter: keep only triangles whose centroid is inside the polygon
        # AND at least one vertex is from the original contour
        triangles = []
        for simplex in tri.simplices:
            p0 = points[simplex[0]]
            p1 = points[simplex[1]]
            p2 = points[simplex[2]]

            cx = (p0[0] + p1[0] + p2[0]) / 3
            cy = (p0[1] + p1[1] + p2[1]) / 3

            if not point_in_polygon(cx, cy, vertices):
                continue

            # Ensure at least one vertex is from the original contour
            has_contour = any(idx < contour_count for idx in simplex)
            if has_contour:
                triangles.append(tuple(int(i) for i in simplex))

        return (all_vertices, triangles)

    except ImportError:
        # Fallback: ear clipping
        return ear_clip_triangulation(vertices)


def ear_clip_triangulation(vertices):
    """Simple ear clipping fallback triangulation"""
    if len(vertices) < 3:
        return (list(vertices), [])

    pts = list(vertices)
    triangles = []
    indices = list(range(len(pts)))

    max_iter = len(pts) * 2
    iteration = 0

    while len(indices) > 3 and iteration < max_iter:
        iteration += 1
        found = False
        n = len(indices)

        for i in range(n):
            prev_idx = indices[(i - 1) % n]
            curr_idx = indices[i]
            next_idx = indices[(i + 1) % n]

            prev = pts[prev_idx]
            curr = pts[curr_idx]
            next = pts[next_idx]

            # Check if this is an ear (convex and no other points inside)
            # Cross product for convexity
            ax = curr[0] - prev[0]
            ay = curr[1] - prev[1]
            bx = next[0] - curr[0]
            by = next[1] - curr[1]
            cross = ax * by - ay * bx

            if cross > EPSILON:  # Convex (CCW)
                # Check no other points inside this ear triangle
                is_ear = True
                for j in range(n):
                    if j == i or j == (i - 1) % n or j == (i + 1) % n:
                        continue
                    test = pts[indices[j]]
                    if point_in_triangle(test, prev, curr, next):
                        is_ear = False
                        break

                if is_ear:
                    triangles.append((prev_idx, curr_idx, next_idx))
                    indices.pop(i)
                    found = True
                    break

        if not found:
            break

    # Final triangle
    if len(indices) == 3:
        triangles.append(tuple(indices))

    return (list(vertices), triangles)


def point_in_triangle(p, a, b, c):
    """Check if point p is inside triangle abc"""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)

    has_neg = (d1 < -EPSILON) or (d2 < -EPSILON) or (d3 < -EPSILON)
    has_pos = (d1 > EPSILON) or (d2 > EPSILON) or (d3 > EPSILON)

    return not (has_neg and has_pos)


# ============================================================================
# Main triangulation entry point
# ============================================================================

def triangulate_polygon_with_holes(outer_vertices, holes):
    """
    Triangulate a polygon with holes.
    
    Algorithm:
    1. Merge all holes into outer using bridge cutting -> single simple polygon
    2. Triangulate the merged polygon using constrained Delaunay
    
    Parameters:
        outer_vertices: list of (x, y) tuples, CCW orientation
        holes: list of hole polygons, each CW orientation
    
    Returns:
        (vertices, triangles) or None
    """
    if len(outer_vertices) < 3:
        return None

    # Filter valid holes
    valid_holes = [h for h in holes if len(h) >= 3]

    if not valid_holes:
        # Simple case: no holes
        return triangulate_simple_polygon(outer_vertices)

    # Merge holes into outer polygon using bridge cutting
    merged = merge_all_holes(outer_vertices, valid_holes)

    # Triangulate merged polygon
    return triangulate_simple_polygon(merged)


def triangulate_nested_tree(root_node):
    """
    Recursively triangulate a nesting tree.
    Each node is triangulated independently, results are combined.
    
    For nested structures like '回':
    - Outer square (level 0, CCW) -> triangulate directly
    - Inner square (level 1, CW hole) -> handled as hole of outer
    - Innermost square (level 2, CCW) -> triangulate independently
    
    For '国':
    - 囗 outer (level 0, CCW) -> triangulate with inner hole
    - 玉 inside (level 2, CCW) -> triangulate independently
    - 丶 inside 玉 (level 3, CW) -> hole of 玉
    """
    all_vertices = []
    all_triangles = []

    def process_node(node, depth=0):
        nonlocal all_vertices, all_triangles

        if node.contour_type == 'outer':
            # This is a filled region - triangulate it
            # Collect direct children that are holes
            hole_children = [c for c in node.children if c.contour_type == 'hole']
            hole_vertices = [c.vertices for c in hole_children]

            result = triangulate_polygon_with_holes(node.vertices, hole_vertices)
            if result and len(result) == 2:
                verts, tris = result
                base = len(all_vertices)
                all_vertices.extend(verts)
                for t in tris:
                    all_triangles.append((t[0] + base, t[1] + base, t[2] + base))

            # Process nested outer contours (deeper levels)
            outer_children = [c for c in node.children if c.contour_type == 'outer']
            for child in outer_children:
                process_node(child, depth + 1)

        elif node.contour_type == 'hole':
            # Holes are handled by their parent outer
            # But may contain nested outers
            outer_children = [c for c in node.children if c.contour_type == 'outer']
            for child in outer_children:
                process_node(child, depth + 1)

    process_node(root_node)
    return (all_vertices, all_triangles)


def triangulate_glyph_contours(contours):
    """
    Main entry point: triangulate all glyph contours.
    
    Steps:
    1. Build nesting tree from contours
    2. For each root in tree, triangulate recursively
    3. Combine all results
    
    Parameters:
        contours: list of dicts with 'points', 'is_ccw', 'abs_area'
    
    Returns:
        (vertices, triangles) or None
    """
    if not contours:
        return None

    # Build nesting tree
    roots = build_nesting_tree(contours)

    if not roots:
        return None

    all_vertices = []
    all_triangles = []

    for root in roots:
        verts, tris = triangulate_nested_tree(root)
        if verts and tris:
            base = len(all_vertices)
            all_vertices.extend(verts)
            for t in tris:
                all_triangles.append((t[0] + base, t[1] + base, t[2] + base))

    if not all_triangles:
        return None

    return (all_vertices, all_triangles)


# ============================================================================
# Post-processing: quality filtering
# ============================================================================

def triangle_min_angle(v0, v1, v2):
    """Calculate minimum angle of triangle in radians"""
    def edge_len(a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    a = edge_len(v1, v2)
    b = edge_len(v0, v2)
    c = edge_len(v0, v1)

    if a < EPSILON or b < EPSILON or c < EPSILON:
        return 0.0

    # Law of cosines
    cos_A = max(-1, min(1, (b ** 2 + c ** 2 - a ** 2) / (2 * b * c)))
    cos_B = max(-1, min(1, (a ** 2 + c ** 2 - b ** 2) / (2 * a * c)))
    cos_C = max(-1, min(1, (a ** 2 + b ** 2 - c ** 2) / (2 * a * b)))

    return min(math.acos(cos_A), math.acos(cos_B), math.acos(cos_C))


def filter_bad_triangles(vertices, triangles, min_angle_deg=10):
    """Remove triangles with very small angles (degenerate triangles)"""
    min_angle_rad = math.radians(min_angle_deg)
    good = []

    for tri in triangles:
        v0 = vertices[tri[0]]
        v1 = vertices[tri[1]]
        v2 = vertices[tri[2]]

        angle = triangle_min_angle(v0, v1, v2)
        if angle >= min_angle_rad:
            good.append(tri)

    return good


def deduplicate_vertices(vertices, triangles, tolerance=1e-6):
    """Merge duplicate vertices and remap triangle indices"""
    seen = {}
    unique = []
    mapping = {}

    for i, v in enumerate(vertices):
        key = (round(v[0], 6), round(v[1], 6))
        if key not in seen:
            seen[key] = len(unique)
            unique.append(v)
        mapping[i] = seen[key]

    remapped = []
    for tri in triangles:
        new_tri = tuple(mapping.get(idx, idx) for idx in tri)
        if len(set(new_tri)) == 3:  # Skip degenerate (duplicate vertex)
            remapped.append(new_tri)

    return unique, remapped


def post_process(vertices, triangles, min_angle_deg=0):
    """Full post-processing pipeline"""
    if not vertices or not triangles:
        return (vertices, triangles)

    # 1. Deduplicate vertices (do this first to avoid index issues)
    vertices, triangles = deduplicate_vertices(vertices, triangles)
    
    # 2. Only filter truly degenerate triangles (area == 0)
    # Don't filter by angle - font glyphs have many thin strokes with sharp angles
    if min_angle_deg > 0:
        triangles = filter_bad_triangles(vertices, triangles, min_angle_deg)

    return (vertices, triangles)
