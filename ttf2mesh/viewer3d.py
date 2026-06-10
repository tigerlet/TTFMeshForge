"""3D Mesh Viewer with rotation and lighting support"""

import math

EPSILON = 1e-10

class Viewer3D:
    """3D mesh viewer with rotation and lighting"""
    
    def __init__(self):
        self.rotation_x = 30.0
        self.rotation_y = 45.0
        self.rotation_z = 0.0
        self.camera_distance = 0.5  # Camera distance for perspective
        self.scale_factor = 500.0  # Additional scaling for glyph display
        self.ambient_light = 0.3
        self.diffuse_light = 0.7
        self.light_direction = (1.0, 1.0, 1.0)
    
    def set_rotation(self, rx, ry, rz):
        """Set rotation angles in degrees"""
        self.rotation_x = rx
        self.rotation_y = ry
        self.rotation_z = rz
    
    def rotate(self, dx, dy):
        """Rotate view by delta angles"""
        self.rotation_y += dx * 0.5
        self.rotation_x += dy * 0.5
        
        # Clamp X rotation
        self.rotation_x = max(-90, min(90, self.rotation_x))
    
    def zoom(self, delta):
        """Zoom in/out by adjusting camera distance"""
        self.camera_distance = max(0.5, min(10.0, self.camera_distance - delta * 0.1))
    
    def _rotate_point(self, x, y, z):
        """Apply rotation transformations to a point"""
        # Convert degrees to radians
        rx = math.radians(self.rotation_x)
        ry = math.radians(self.rotation_y)
        rz = math.radians(self.rotation_z)
        
        # Rotate around X axis
        cos_rx = math.cos(rx)
        sin_rx = math.sin(rx)
        y1 = y * cos_rx - z * sin_rx
        z1 = y * sin_rx + z * cos_rx
        
        # Rotate around Y axis
        cos_ry = math.cos(ry)
        sin_ry = math.sin(ry)
        x2 = x * cos_ry + z1 * sin_ry
        z2 = -x * sin_ry + z1 * cos_ry
        
        # Rotate around Z axis
        cos_rz = math.cos(rz)
        sin_rz = math.sin(rz)
        x3 = x2 * cos_rz - y1 * sin_rz
        y3 = x2 * sin_rz + y1 * cos_rz
        
        return (x3, y3, z2)
    
    def _project(self, x, y, z):
        """Project 3D point to 2D using orthographic projection"""
        # Apply scaling first
        x_scaled = x * self.scale_factor
        y_scaled = y * self.scale_factor
        z_scaled = z * self.scale_factor
        
        # Apply rotation
        rx, ry, rz = self._rotate_point(x_scaled, y_scaled, z_scaled)
        
        # Apply orthographic projection (simpler and more stable)
        # Use isometric-style projection: project X and Y, with Z affecting both
        px = rx - rz * 0.5
        py = ry - rz * 0.3
        
        return (px, py, rz)
    
    def _calculate_face_color(self, face, mesh):
        """Calculate face color based on normal and lighting"""
        if not mesh.normals:
            return '#6699cc'
        
        # Use average normal of face vertices
        nx = ny = nz = 0.0
        for v in face:
            n = mesh.normals[v]
            nx += n[0]
            ny += n[1]
            nz += n[2]
        
        # Normalize
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length < EPSILON:
            return '#6699cc'
        
        nx /= length
        ny /= length
        nz /= length
        
        # Normalize light direction
        lx, ly, lz = self.light_direction
        l_length = math.sqrt(lx * lx + ly * ly + lz * lz)
        if l_length > EPSILON:
            lx /= l_length
            ly /= l_length
            lz /= l_length
        
        # Calculate dot product for diffuse lighting
        dot = max(0.0, nx * lx + ny * ly + nz * lz)
        intensity = self.ambient_light + self.diffuse_light * dot
        
        # Clamp intensity
        intensity = max(0.0, min(1.0, intensity))
        
        # Convert to RGB color
        r = int(102 * intensity)
        g = int(153 * intensity)
        b = int(204 * intensity)
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def render(self, mesh, canvas, width, height, view_mode='solid'):
        """Render 3D mesh to canvas"""
        if not mesh or not mesh.vert:
            return
        
        # Project all vertices
        projected = []
        depths = []
        for v in mesh.vert:
            px, py, pz = self._project(v[0], v[1], v[2])
            projected.append((px, py))
            depths.append(pz)
        
        # Get bounds
        pxs = [p[0] for p in projected]
        pys = [p[1] for p in projected]
        
        if not pxs or not pys:
            return
        
        min_px, max_px = min(pxs), max(pxs)
        min_py, max_py = min(pys), max(pys)
        
        p_width = max(1.0, max_px - min_px)
        p_height = max(1.0, max_py - min_py)
        
        # Calculate scale and offset
        p_scale = min(width / p_width, height / p_height) * 0.9
        p_center_x = (min_px + max_px) / 2
        p_center_y = (min_py + max_py) / 2
        offset_x = width // 2
        offset_y = height // 2
        
        if view_mode == 'solid':
            # Sort faces by depth (back to front)
            face_info = []
            for idx, face in enumerate(mesh.faces):
                # Calculate average depth
                avg_depth = sum(depths[v] for v in face) / 3
                face_info.append((idx, avg_depth))
            
            # Sort by depth (back to front)
            face_info.sort(key=lambda fi: fi[1])
            
            # Draw faces
            for idx, _ in face_info:
                face = mesh.faces[idx]
                pts = []
                for v in face:
                    px, py = projected[v]
                    x = (px - p_center_x) * p_scale + offset_x
                    y = -(py - p_center_y) * p_scale + offset_y
                    pts.append((x, y))
                
                color = self._calculate_face_color(face, mesh)
                canvas.create_polygon(pts, fill=color, outline='#336699', width=0.5)
        else:
            # Wireframe mode
            edges = set()
            for face in mesh.faces:
                for i in range(3):
                    v1 = face[i]
                    v2 = face[(i + 1) % 3]
                    edge = tuple(sorted([v1, v2]))
                    edges.add(edge)
            
            # Draw edges
            for v1, v2 in edges:
                px1, py1 = projected[v1]
                px2, py2 = projected[v2]
                
                x1 = (px1 - p_center_x) * p_scale + offset_x
                y1 = -(py1 - p_center_y) * p_scale + offset_y
                x2 = (px2 - p_center_x) * p_scale + offset_x
                y2 = -(py2 - p_center_y) * p_scale + offset_y
                
                canvas.create_line(x1, y1, x2, y2, fill='#336699', width=1)
    
    def get_projected_points(self, mesh):
        """Get projected 2D points for all vertices"""
        projected = []
        for v in mesh.vert:
            px, py, _ = self._project(v[0], v[1], v[2])
            projected.append((px, py))
        return projected