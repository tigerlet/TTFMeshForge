import math
from .core import *
from .outline import *

EPSILON = 1e-10


class TriEdge:
    """Edge in triangulation"""
    def __init__(self, v1=-1, v2=-1):
        self.v1 = v1
        self.v2 = v2
        self.face1 = -1
        self.face2 = -1
    
    def __eq__(self, other):
        if isinstance(other, TriEdge):
            return (self.v1 == other.v1 and self.v2 == other.v2) or \
                   (self.v1 == other.v2 and self.v2 == other.v1)
        return False
    
    def __hash__(self):
        return hash(tuple(sorted([self.v1, self.v2])))


class Mesher:
    """Triangulation mesher class"""
    
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.edges = []
        self.outline = None
        self.quality = 0
        self.features = 0
        self.constraints = []
    
    def add_vertex(self, x, y):
        """Add a vertex"""
        self.vertices.append(TTFTriPoint(x, y))
        return len(self.vertices) - 1
    
    def add_face(self, v0, v1, v2):
        """Add a triangular face"""
        face = (v0, v1, v2)
        self.faces.append(face)
        return len(self.faces) - 1
    
    def remove_face(self, idx):
        """Remove a face"""
        if idx < len(self.faces):
            self.faces[idx] = None
    
    def find_edge(self, v1, v2):
        """Find edge by vertices"""
        for i, edge in enumerate(self.edges):
            if edge is not None and ((edge.v1 == v1 and edge.v2 == v2) or
                                    (edge.v1 == v2 and edge.v2 == v1)):
                return i
        return -1
    
    def add_edge(self, v1, v2, face_idx):
        """Add or update an edge"""
        idx = self.find_edge(v1, v2)
        if idx >= 0:
            edge = self.edges[idx]
            if edge.face1 == -1:
                edge.face1 = face_idx
            else:
                edge.face2 = face_idx
        else:
            edge = TriEdge(v1, v2)
            edge.face1 = face_idx
            self.edges.append(edge)
    
    def circumcenter(self, v0, v1, v2):
        """Calculate circumcenter of triangle"""
        p0 = self.vertices[v0]
        p1 = self.vertices[v1]
        p2 = self.vertices[v2]
        
        d = 2.0 * (p0.x * (p1.y - p2.y) + p1.x * (p2.y - p0.y) + p2.x * (p0.y - p1.y))
        
        if abs(d) < EPSILON:
            return None
        
        ax = p0.x ** 2 + p0.y ** 2
        ay = p1.x ** 2 + p1.y ** 2
        az = p2.x ** 2 + p2.y ** 2
        
        cx = (ax * (p1.y - p2.y) + ay * (p2.y - p0.y) + az * (p0.y - p1.y)) / d
        cy = (ax * (p2.x - p1.x) + ay * (p0.x - p2.x) + az * (p1.x - p0.x)) / d
        
        return (cx, cy)
    
    def circumradius(self, v0, v1, v2):
        """Calculate circumradius of triangle"""
        center = self.circumcenter(v0, v1, v2)
        if center is None:
            return float('inf')
        
        p0 = self.vertices[v0]
        dx = p0.x - center[0]
        dy = p0.y - center[1]
        return math.sqrt(dx * dx + dy * dy)
    
    def point_in_circle(self, v0, v1, v2, v3):
        """Check if point v3 is inside circumcircle of triangle v0-v1-v2"""
        center = self.circumcenter(v0, v1, v2)
        if center is None:
            return False
        
        p3 = self.vertices[v3]
        dx = p3.x - center[0]
        dy = p3.y - center[1]
        dist_sq = dx * dx + dy * dy
        
        p0 = self.vertices[v0]
        rad_sq = (p0.x - center[0]) ** 2 + (p0.y - center[1]) ** 2
        
        return dist_sq < rad_sq - EPSILON
    
    def triangle_area(self, v0, v1, v2):
        """Calculate area of triangle"""
        p0 = self.vertices[v0]
        p1 = self.vertices[v1]
        p2 = self.vertices[v2]
        
        return abs((p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y)) / 2.0
    
    def legalize_edge(self, face_idx, edge_idx):
        """Legalize an edge (Delaunay flip)"""
        if edge_idx >= len(self.edges):
            return False
        
        edge = self.edges[edge_idx]
        if edge is None:
            return False
        
        if edge.face1 == -1 or edge.face2 == -1:
            return False
        
        # Check bounds
        if edge.face1 >= len(self.faces) or edge.face2 >= len(self.faces):
            return False
        
        f1 = self.faces[edge.face1]
        f2 = self.faces[edge.face2]
        
        if f1 is None or f2 is None:
            return False
        
        # Find opposite vertices
        def find_opposite(face, v1, v2):
            for v in face:
                if v != v1 and v != v2:
                    return v
            return -1
        
        v_opp1 = find_opposite(f1, edge.v1, edge.v2)
        v_opp2 = find_opposite(f2, edge.v1, edge.v2)
        
        if v_opp1 == -1 or v_opp2 == -1:
            return False
        
        # Check if edge needs to be flipped
        if self.point_in_circle(v_opp1, edge.v1, edge.v2, v_opp2):
            # Remove old faces
            self.faces[edge.face1] = None
            self.faces[edge.face2] = None
            
            # Remove old edge references from other edges
            for i, e in enumerate(self.edges):
                if e is None:
                    continue
                if e.face1 == edge.face1:
                    e.face1 = -1
                if e.face2 == edge.face1:
                    e.face2 = -1
                if e.face1 == edge.face2:
                    e.face1 = -1
                if e.face2 == edge.face2:
                    e.face2 = -1
            
            # Create new faces
            new_f1 = self.add_face(v_opp1, edge.v1, v_opp2)
            new_f2 = self.add_face(v_opp1, v_opp2, edge.v2)
            
            # Update edges
            self.edges[edge_idx].v1 = v_opp1
            self.edges[edge_idx].v2 = v_opp2
            self.edges[edge_idx].face1 = new_f1
            self.edges[edge_idx].face2 = new_f2
            
            # Add new edges
            self.add_edge(v_opp1, edge.v1, new_f1)
            self.add_edge(edge.v1, v_opp2, new_f1)
            self.add_edge(v_opp1, v_opp2, new_f2)
            self.add_edge(v_opp2, edge.v2, new_f2)
            
            return True
        
        return False
    
    def optimize_delaunay(self):
        """Optimize triangulation to be Delaunay"""
        changed = True
        iterations = 0
        
        while changed and iterations < 100:
            changed = False
            iterations += 1
            
            for i, edge in enumerate(self.edges):
                if edge is None:
                    continue
                
                if edge.face1 != -1 and edge.face2 != -1:
                    if self.legalize_edge(i, i):
                        changed = True
        
        # Clean up None faces
        self.faces = [f for f in self.faces if f is not None]
    
    def sweep_line_triangulation(self):
        """Triangulate using sweep line algorithm"""
        if len(self.vertices) < 3:
            return
        
        # Sort vertices by x, then y
        sorted_indices = sorted(range(len(self.vertices)), 
                               key=lambda i: (self.vertices[i].x, self.vertices[i].y))
        
        # Find bounding box
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Add super triangle that encloses all points
        super_size = max(max_x - min_x, max_y - min_y) * 2
        v0 = len(self.vertices)
        v1 = len(self.vertices) + 1
        v2 = len(self.vertices) + 2
        self.add_vertex(min_x - super_size, min_y - super_size)
        self.add_vertex(max_x + super_size, min_y - super_size)
        self.add_vertex((min_x + max_x) / 2, max_y + super_size)
        
        # Start with super triangle
        self.add_face(v0, v1, v2)
        self.add_edge(v0, v1, 0)
        self.add_edge(v1, v2, 0)
        self.add_edge(v2, v0, 0)
        
        # Add each point
        for v_new in sorted_indices:
            p_new = self.vertices[v_new]
            
            # Find faces that contain the point
            bad_faces = []
            
            for j, face in enumerate(self.faces):
                if face is None:
                    continue
                
                # Check if point is inside the face (using barycentric or simple check)
                v1_idx, v2_idx, v3_idx = face
                p1 = self.vertices[v1_idx]
                p2 = self.vertices[v2_idx]
                p3 = self.vertices[v3_idx]
                
                # Barycentric check
                v0 = (p2.x - p1.x) * (p_new.y - p1.y) - (p2.y - p1.y) * (p_new.x - p1.x)
                v1 = (p3.x - p2.x) * (p_new.y - p2.y) - (p3.y - p2.y) * (p_new.x - p2.x)
                v2 = (p1.x - p3.x) * (p_new.y - p3.y) - (p1.y - p3.y) * (p_new.x - p3.x)
                
                has_neg = (v0 < -EPSILON) or (v1 < -EPSILON) or (v2 < -EPSILON)
                has_pos = (v0 > EPSILON) or (v1 > EPSILON) or (v2 > EPSILON)
                
                if not (has_neg and has_pos):
                    bad_faces.append(j)
            
            # Collect boundary edges
            boundary = set()
            
            for face_idx in bad_faces:
                face = self.faces[face_idx]
                if face is None:
                    continue
                
                for k in range(3):
                    e1, e2 = face[k], face[(k + 1) % 3]
                    edge = tuple(sorted([e1, e2]))
                    
                    # Check if this edge is shared with another face
                    shared = False
                    for other_idx, other_face in enumerate(self.faces):
                        if other_idx == face_idx or other_face is None:
                            continue
                        
                        other_set = set(other_face)
                        if e1 in other_set and e2 in other_set:
                            shared = True
                            break
                    
                    if not shared:
                        boundary.add(edge)
            
            # Remove bad faces
            for face_idx in reversed(bad_faces):
                self.faces[face_idx] = None
            
            # Create new faces from boundary edges
            for edge in boundary:
                e1, e2 = edge
                if e1 != v_new and e2 != v_new:
                    new_face_idx = self.add_face(v_new, e1, e2)
                    self.add_edge(v_new, e1, new_face_idx)
                    self.add_edge(e1, e2, new_face_idx)
                    self.add_edge(e2, v_new, new_face_idx)
        
        # Store super triangle vertex indices for later removal
        self.super_vertices = [v0, v1, v2]
    
    def prepare_outline_constraints(self, outline):
        """Prepare constraints from outline"""
        self.outline = outline
        self.constraints = []
        
        for contour in outline.contours:
            for i in range(len(contour.points)):
                p1 = contour.points[i]
                p2 = contour.points[(i + 1) % len(contour.points)]
                
                # Find vertex indices
                v1 = -1
                v2 = -1
                
                for j, v in enumerate(self.vertices):
                    if abs(v.x - p1.x) < EPSILON and abs(v.y - p1.y) < EPSILON:
                        v1 = j
                    if abs(v.x - p2.x) < EPSILON and abs(v.y - p2.y) < EPSILON:
                        v2 = j
                
                if v1 != -1 and v2 != -1:
                    self.constraints.append((v1, v2))
    
    def triangulate(self, outline):
        """Main triangulation function"""
        # Add all outline points as vertices
        for contour in outline.contours:
            for pt in contour.points:
                self.add_vertex(pt.x, pt.y)
        
        # Prepare constraints
        self.prepare_outline_constraints(outline)
        
        # Initial triangulation
        self.sweep_line_triangulation()
        
        # Delaunay optimization
        self.optimize_delaunay()
        
        # Remove triangles outside the outline
        self.remove_exterior_triangles(outline)
        
        return True
    
    def remove_exterior_triangles(self, outline):
        """Remove triangles that are outside the outline"""
        faces_to_remove = []
        
        for i, face in enumerate(self.faces):
            if face is None:
                continue
            
            # Calculate centroid
            p0 = self.vertices[face[0]]
            p1 = self.vertices[face[1]]
            p2 = self.vertices[face[2]]
            
            cx = (p0.x + p1.x + p2.x) / 3.0
            cy = (p0.y + p1.y + p2.y) / 3.0
            
            # Check if centroid is inside the outline
            if not ttf_outline_evenodd(outline, [cx, cy]):
                faces_to_remove.append(i)
        
        # Remove faces in reverse order
        for i in reversed(faces_to_remove):
            self.faces[i] = None
        
        # Clean up
        self.faces = [f for f in self.faces if f is not None]
    
    def to_mesh(self):
        """Convert to TTFTriMesh"""
        mesh = TTFTriMesh()
        
        # Remove faces that use super triangle vertices
        if hasattr(self, 'super_vertices'):
            super_set = set(self.super_vertices)
            valid_faces = [f for f in self.faces if f is not None and not super_set.intersection(f)]
        else:
            valid_faces = [f for f in self.faces if f is not None]
        
        # Copy vertices (exclude super triangle vertices if present)
        if hasattr(self, 'super_vertices'):
            # Create mapping from old indices to new indices
            super_set = set(self.super_vertices)
            valid_vertices = []
            index_map = {}
            new_idx = 0
            for i, v in enumerate(self.vertices):
                if i not in super_set:
                    valid_vertices.append(v)
                    index_map[i] = new_idx
                    new_idx += 1
            
            mesh.vert = [(v.x, v.y) for v in valid_vertices]
            mesh.nvert = len(mesh.vert)
            
            # Remap face indices
            mesh.faces = []
            for face in valid_faces:
                new_face = [index_map[v] for v in face]
                mesh.faces.append(new_face)
            mesh.nfaces = len(mesh.faces)
        else:
            mesh.vert = [(v.x, v.y) for v in self.vertices]
            mesh.nvert = len(mesh.vert)
            mesh.faces = [list(f) for f in valid_faces]
            mesh.nfaces = len(mesh.faces)
        
        # Add outline reference
        mesh.outline = self.outline
        
        # Calculate face normals for smooth shading
        mesh.face_normals = []
        for face in self.faces:
            v0 = self.vertices[face[0]]
            v1 = self.vertices[face[1]]
            v2 = self.vertices[face[2]]
            
            # Normal vector in 2D is perpendicular to edge
            edge1_x = v1.x - v0.x
            edge1_y = v1.y - v0.y
            
            # 2D "normal" pointing outward
            mesh.face_normals.append((-edge1_y, edge1_x))
        
        return mesh


def ttf_glyph2mesh(glyph, quality=TTF_QUALITY_NORMAL, features=0):
    """Convert glyph to 2D mesh using shapely-based triangulation (same as font2tri_lib.py)"""
    if glyph.outline is None:
        return None
    
    # Import necessary modules
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
        import numpy as np
    except ImportError:
        return _ttf_glyph2mesh_fallback(glyph, quality, features)
    
    # Calculate bounding box from original outline to determine scaling factor
    all_points = []
    for contour in glyph.outline.contours:
        for pt in contour.points:
            all_points.append((pt.x, pt.y))
    
    if not all_points:
        return None
    
    xs = [x for x, y in all_points]
    ys = [y for x, y in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    width = max_x - min_x
    height = max_y - min_y
    
    # Scale coordinates to avoid precision issues with very small values
    target_size = 1000.0
    scale = target_size / max(width, height) if max(width, height) > EPSILON else 1.0
    
    # Create a temporary scaled outline for processing
    scaled_outline = TTFOutline()
    
    for src_contour in glyph.outline.contours:
        contour = TTFContour()
        scaled_points = []
        for pt in src_contour.points:
            new_pt = TTFTriPoint(pt.x * scale, pt.y * scale)
            new_pt.onc = pt.onc
            scaled_points.append(new_pt)
        
        # Ensure contour is closed
        if len(scaled_points) >= 2:
            first = scaled_points[0]
            last = scaled_points[-1]
            if abs(first.x - last.x) > EPSILON or abs(first.y - last.y) > EPSILON:
                close_pt = TTFTriPoint(first.x, first.y)
                close_pt.onc = first.onc
                scaled_points.append(close_pt)
        
        contour.points = scaled_points
        scaled_outline.contours.append(contour)
    
    # Create a temporary glyph with scaled outline for linearization
    temp_glyph = TTFGlyph()
    temp_glyph.outline = scaled_outline
    
    # Create linearized outline from scaled glyph
    outline = ttf_linear_outline(temp_glyph, quality)
    if outline is None or len(outline.contours) == 0:
        return None
    
    # Extract all contour points (same as font2tri_lib.py)
    contours = []
    for contour in outline.contours:
        points = [(pt.x, pt.y) for pt in contour.points]
        if len(points) >= 3:
            contours.append(np.array(points))
    
    if not contours:
        return None
    
    # === Step 1: Calculate area for each contour ===
    def contour_area(c):
        return 0.5 * np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1])
    
    areas = [contour_area(c) for c in contours]
    
    # === Step 2: Build vmap and vertices from contour points ===
    vmap = {}
    vertices = []
    
    for c in contours:
        for x, y in c:
            key = (round(x, 3), round(y, 3))
            if key not in vmap:
                vmap[key] = len(vertices)
                vertices.append([x, y])
    
    # === Step 3: Separate outer and inner contours ===
    outer_indices = [i for i in range(len(contours)) if areas[i] < 0]
    outer_indices.sort(key=lambda i: areas[i])
    
    inner_indices = [i for i in range(len(contours)) if areas[i] >= 0]
    inner_indices.sort(key=lambda i: -areas[i])
    
    # === Step 4: Build components ===
    processed = []
    for i in range(len(contours)):
        coords = contours[i]
        if len(coords) < 3:
            continue
        
        area = contour_area(coords)
        is_outer = area < 0
        
        poly = Polygon(coords).buffer(0)
        processed.append({
            "index": i,
            "polygon": poly,
            "is_outer": is_outer,
            "children": []
        })
    
    # Sort by area (largest first)
    processed.sort(key=lambda x: x["polygon"].area, reverse=True)
    
    # Build hierarchy
    hierarchy = []
    for poly in processed:
        if poly["is_outer"]:
            hierarchy.insert(0, poly)
    
    for poly in processed:
        if not poly["is_outer"]:
            for parent in hierarchy:
                if parent["polygon"].contains(poly["polygon"]):
                    parent["children"].append(poly)
                    break
    
    # Convert to components list
    components = []
    for outer in hierarchy:
        inner_list = [child["index"] for child in outer["children"]]
        components.append((outer["index"], inner_list))
    
    faces = []
    
    # === Step 5: Triangulate each component ===
    for outer_idx, inner_indices_list in components:
        outer = contours[outer_idx]
        holes = []
        
        for inner_idx in inner_indices_list:
            inner = contours[inner_idx]
            holes.append(inner)
        
        try:
            poly = Polygon(outer, holes=holes)
            outer_poly = Polygon(outer)
            inner_polys = [Polygon(contours[i]) for i in inner_indices_list]
            
            for t in triangulate(poly):
                tri_pts = np.array(list(t.exterior.coords)[:-1])
                if len(tri_pts) != 3:
                    continue
                
                tri_poly = Polygon(tri_pts)
                
                clipped_tri = tri_poly.intersection(outer_poly)
                
                for inner_poly in inner_polys:
                    clipped_tri = clipped_tri.difference(inner_poly)
                
                if clipped_tri.is_empty:
                    continue
                
                if hasattr(clipped_tri, 'exterior'):
                    coords = np.array(list(clipped_tri.exterior.coords)[:-1])
                    if len(coords) >= 3:
                        clipped_poly = Polygon(coords)
                        for sub_t in triangulate(clipped_poly):
                            sub_tri_pts = np.array(list(sub_t.exterior.coords)[:-1])
                            if len(sub_tri_pts) == 3:
                                idx = []
                                for (x, y) in sub_tri_pts:
                                    k = (round(x, 3), round(y, 3))
                                    if k not in vmap:
                                        vmap[k] = len(vertices)
                                        vertices.append([x, y])
                                    idx.append(vmap[k])
                                if len(idx) == 3:
                                    faces.append(idx)
                elif hasattr(clipped_tri, 'geoms'):
                    for geom in clipped_tri.geoms:
                        if hasattr(geom, 'exterior'):
                            coords = np.array(list(geom.exterior.coords)[:-1])
                            if len(coords) >= 3:
                                clipped_poly = Polygon(coords)
                                for sub_t in triangulate(clipped_poly):
                                    sub_tri_pts = np.array(list(sub_t.exterior.coords)[:-1])
                                    if len(sub_tri_pts) == 3:
                                        idx = []
                                        for (x, y) in sub_tri_pts:
                                            k = (round(x, 3), round(y, 3))
                                            if k not in vmap:
                                                vmap[k] = len(vertices)
                                                vertices.append([x, y])
                                            idx.append(vmap[k])
                                        if len(idx) == 3:
                                            faces.append(idx)
        except Exception as e:
            print(f"Error processing component {outer_idx}: {e}")
            continue
    
    if not faces:
        return None
    
    # Create mesh
    mesh = TTFTriMesh()
    mesh.vert = [(v[0], v[1]) for v in vertices]
    mesh.nvert = len(mesh.vert)
    mesh.faces = faces
    mesh.nfaces = len(mesh.faces)
    
    # Scale mesh back to original size
    inv_scale = 1.0 / scale
    for i in range(len(mesh.vert)):
        mesh.vert[i] = (mesh.vert[i][0] * inv_scale, mesh.vert[i][1] * inv_scale)
    
    return mesh


def _ttf_glyph2mesh_fallback(glyph, quality=TTF_QUALITY_NORMAL, features=0):
    """Fallback triangulation using earclipping when shapely is not available"""
    if glyph.outline is None:
        return None
    
    all_points = []
    for contour in glyph.outline.contours:
        for pt in contour.points:
            all_points.append((pt.x, pt.y))
    
    if not all_points:
        return None
    
    xs = [x for x, y in all_points]
    ys = [y for x, y in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    width = max_x - min_x
    height = max_y - min_y
    
    target_size = 1000.0
    scale = target_size / max(width, height) if max(width, height) > EPSILON else 1.0
    
    scaled_outline = TTFOutline()
    
    for src_contour in glyph.outline.contours:
        contour = TTFContour()
        scaled_points = []
        for pt in src_contour.points:
            new_pt = TTFTriPoint(pt.x * scale, pt.y * scale)
            new_pt.onc = pt.onc
            scaled_points.append(new_pt)
        
        if len(scaled_points) >= 2:
            first = scaled_points[0]
            last = scaled_points[-1]
            if abs(first.x - last.x) > EPSILON or abs(first.y - last.y) > EPSILON:
                close_pt = TTFTriPoint(first.x, first.y)
                close_pt.onc = first.onc
                scaled_points.append(close_pt)
        
        contour.points = scaled_points
        scaled_outline.contours.append(contour)
    
    temp_glyph = TTFGlyph()
    temp_glyph.outline = scaled_outline
    
    outline = ttf_linear_outline(temp_glyph, quality)
    if outline is None or len(outline.contours) == 0:
        return None
    
    from .earclipping import triangulate_glyph_contours, post_process
    
    def signed_area(points):
        area = 0.0
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i+1)%n]
            area += (x1 * y2) - (x2 * y1)
        return area / 2.0
    
    all_contours = []
    for idx, contour in enumerate(outline.contours):
        points = [(pt.x, pt.y) for pt in contour.points]
        if len(points) >= 3:
            area = signed_area(points)
            all_contours.append({
                'points': points,
                'area': area,
                'is_ccw': area < 0,
                'abs_area': abs(area),
                'index': idx
            })
    
    if not all_contours:
        return None
    
    all_contours.sort(key=lambda c: c['abs_area'], reverse=True)
    
    result = triangulate_glyph_contours(all_contours)
    
    if not result or len(result) != 2:
        return None
    
    vertices, triangles = result
    vertices, triangles = post_process(vertices, triangles, min_angle_deg=0)
    
    if not triangles:
        return None
    
    mesh = TTFTriMesh()
    mesh.vert = vertices
    mesh.nvert = len(mesh.vert)
    mesh.faces = [list(t) for t in triangles]
    mesh.nfaces = len(mesh.faces)
    
    inv_scale = 1.0 / scale
    for i in range(len(mesh.vert)):
        mesh.vert[i] = (mesh.vert[i][0] * inv_scale, mesh.vert[i][1] * inv_scale)
    
    return mesh


def mesh_to_obj(mesh, filename):
    """Export mesh to Wavefront OBJ format"""
    if mesh is None:
        return False
    
    try:
        with open(filename, 'w') as f:
            # Write vertices
            for v in mesh.vert:
                f.write(f'v {v[0]:.6f} {v[1]:.6f} 0.0\n')
            
            # Write faces (OBJ indices start at 1)
            for face in mesh.faces:
                f.write(f'f {face[0]+1} {face[1]+1} {face[2]+1}\n')
        
        return True
    except:
        return False


def mesh_to_stl(mesh, filename):
    """Export mesh to STL format"""
    if mesh is None:
        return False
    
    try:
        with open(filename, 'wb') as f:
            # Header
            header = b'Generated by ttf2mesh' + b'\x00' * (80 - 20)
            f.write(header)
            
            # Number of triangles
            f.write(struct.pack('<I', mesh.nfaces))
            
            # Write each triangle
            for face in mesh.faces:
                v0 = mesh.vert[face[0]]
                v1 = mesh.vert[face[1]]
                v2 = mesh.vert[face[2]]
                
                # Normal (0, 0, 1) for all faces in XY plane
                f.write(struct.pack('<fff', 0.0, 0.0, 1.0))
                
                # Vertices
                f.write(struct.pack('<fff', v0[0], v0[1], 0.0))
                f.write(struct.pack('<fff', v1[0], v1[1], 0.0))
                f.write(struct.pack('<fff', v2[0], v2[1], 0.0))
                
                # Attribute byte count
                f.write(struct.pack('<H', 0))
        
        return True
    except:
        return False
