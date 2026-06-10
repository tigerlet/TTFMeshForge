#!/usr/bin/env python3
"""TTFMeshForge - TrueType Font to Mesh Converter GUI"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ttf2mesh import *
from ttf2mesh.viewer3d import Viewer3D


class TTFFontViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("TTFMeshForge - Font Mesh Generator")
        self.root.geometry("1000x750")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        
        self.font = None
        self.current_glyph = None
        self.mesh2d = None
        self.mesh3d = None
        self.system_fonts = []
        
        # 3D Viewer
        self.viewer3d = Viewer3D()
        self.dragging = False
        self.last_x = 0
        self.last_y = 0
        
        self.font_path_var = tk.StringVar()
        self.char_input_var = tk.StringVar(value='A')
        self.quality_var = tk.IntVar(value=TTF_QUALITY_NORMAL)
        self.depth_var = tk.DoubleVar(value=0.1)
        self.font_family_var = tk.StringVar(value="")
        
        self.create_widgets()
    
    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TFrame', padding=6, background='#f5f5f5')
        style.configure('TLabelFrame', padding=10, background='#f5f5f5', borderwidth=1)
        style.configure('TButton', padding=6, font=('Segoe UI', 10))
        style.configure('TLabel', font=('Segoe UI', 10), background='#f5f5f5')
        style.configure('TEntry', font=('Segoe UI', 10), padding=4)
        style.configure('TCombobox', font=('Segoe UI', 10), padding=4)
        style.configure('TRadiobutton', font=('Segoe UI', 10), background='#f5f5f5')
        
        style.map('TButton',
                  foreground=[('pressed', '#fff'), ('active', '#333')],
                  background=[('pressed', '#2c5282'), ('active', '#ebf8ff')])
        
        self.root.configure(bg='#f5f5f5')
        
        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        top_frame.columnconfigure(0, weight=1)
        
        font_row_frame = ttk.Frame(top_frame)
        font_row_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        font_row_frame.columnconfigure(1, weight=1)
        
        ttk.Label(font_row_frame, text="Font:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        font_entry = ttk.Entry(font_row_frame, textvariable=self.font_path_var, font=('Segoe UI', 10))
        font_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 8))
        ttk.Button(font_row_frame, text="Browse...", command=self.browse_font, width=12).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(font_row_frame, text="System Fonts", command=self.select_system_font, width=14).grid(row=0, column=3)
        
        settings_row_frame = ttk.Frame(top_frame)
        settings_row_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        char_input_frame = ttk.Frame(settings_row_frame)
        char_input_frame.grid(row=0, column=0, padx=(0, 20))
        
        ttk.Label(char_input_frame, text="Character:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.char_entry = ttk.Entry(char_input_frame, textvariable=self.char_input_var, width=8, font=('Segoe UI', 18, 'bold'))
        self.char_entry.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(char_input_frame, text="Preview", command=self.update_preview, width=10).grid(row=0, column=2)
        self.char_entry.bind('<Return>', lambda e: self.update_preview())
        
        quality_frame = ttk.Frame(settings_row_frame)
        quality_frame.grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(quality_frame, text="Quality:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.quality_combo = ttk.Combobox(quality_frame, 
                                          values=['Low', 'Normal', 'High'],
                                          state='readonly', width=8)
        self.quality_combo.current(1)
        self.quality_combo.grid(row=0, column=1)
        
        self.quality_map = {
            'Low': TTF_QUALITY_LOW,
            'Normal': TTF_QUALITY_NORMAL,
            'High': TTF_QUALITY_HIGH
        }
        
        depth_frame = ttk.Frame(settings_row_frame)
        depth_frame.grid(row=0, column=2, padx=(0, 20))
        
        ttk.Label(depth_frame, text="Extrusion Depth:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.depth_entry = ttk.Entry(depth_frame, textvariable=self.depth_var, width=8, font=('Segoe UI', 10))
        self.depth_entry.grid(row=0, column=1)
        
        view_mode_frame = ttk.Frame(settings_row_frame)
        view_mode_frame.grid(row=0, column=3)
        
        self.view_mode_var = tk.StringVar(value='wireframe')
        ttk.Label(view_mode_frame, text="View:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Radiobutton(view_mode_frame, text="Wireframe", variable=self.view_mode_var, value='wireframe', 
                        command=self.redraw_mesh_preview).grid(row=0, column=1, padx=(0, 8))
        ttk.Radiobutton(view_mode_frame, text="Solid", variable=self.view_mode_var, value='solid',
                        command=self.redraw_mesh_preview).grid(row=0, column=2)
        
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(1, weight=1)
        
        left_pane = ttk.Frame(paned_window, width=280, height=400)
        paned_window.add(left_pane, weight=1)
        
        preview_frame = ttk.LabelFrame(left_pane, text=" Glyph Preview ", labelanchor='nw')
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        self.preview_canvas = tk.Canvas(preview_frame, bg='white', borderwidth=1, relief='solid', highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        middle_pane = ttk.Frame(paned_window, width=400, height=400)
        paned_window.add(middle_pane, weight=2)
        
        mesh_preview_frame = ttk.LabelFrame(middle_pane, text=" Mesh Preview ", labelanchor='nw')
        mesh_preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        mesh_preview_frame.columnconfigure(0, weight=2)
        mesh_preview_frame.rowconfigure(0, weight=1)
        
        self.mesh_canvas = tk.Canvas(mesh_preview_frame, bg='#ffffff', borderwidth=1, relief='solid', highlightthickness=0)
        self.mesh_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.mesh_canvas.create_text(140, 140, text="Generate a mesh\nto preview", 
                                    fill='#999', font=('Segoe UI', 11), justify='center')
        
        self.mesh_canvas.bind('<ButtonPress-1>', self.on_mouse_down)
        self.mesh_canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.mesh_canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.mesh_canvas.bind('<MouseWheel>', self.on_mouse_wheel)
        self.mesh_canvas.bind('<Button-4>', self.on_mouse_wheel)
        self.mesh_canvas.bind('<Button-5>', self.on_mouse_wheel)
        
        view_controls_frame = ttk.Frame(mesh_preview_frame)
        view_controls_frame.grid(row=1, column=0, pady=(5, 5))
        
        preset_buttons = [
            ('Front', 'front'),
            ('Back', 'back'),
            ('Left', 'left'),
            ('Right', 'right'),
            ('Top', 'top'),
            ('Bottom', 'bottom'),
            ('Iso', 'isometric')
        ]
        
        button_frame = ttk.Frame(view_controls_frame)
        button_frame.grid(row=0, column=0)
        
        for i, (text, preset) in enumerate(preset_buttons):
            btn = ttk.Button(button_frame, text=text, width=6, padding=4,
                            command=lambda p=preset: self.set_view_preset(p))
            btn.grid(row=0, column=i, padx=2)
        
        reset_btn = ttk.Button(view_controls_frame, text="Reset View", 
                              command=self.reset_view, padding=4)
        reset_btn.grid(row=1, column=0, pady=3)
        
        right_pane = ttk.Frame(paned_window, width=180, height=400)
        paned_window.add(right_pane, weight=0)
        
        info_frame = ttk.LabelFrame(right_pane, text=" Mesh Information ", labelanchor='nw')
        info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        self.info_text = scrolledtext.ScrolledText(info_frame, wrap=tk.WORD, 
                                                   font=('Segoe UI', 9),
                                                   bg='#ffffff', borderwidth=1)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.info_text.insert(tk.END, "Load a font and select a character\nto see mesh information.\n")
        self.info_text.config(state='disabled')
        
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        bottom_frame.columnconfigure(0, weight=1)
        
        action_frame = ttk.LabelFrame(bottom_frame, text=" Actions ", labelanchor='nw')
        action_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        gen_buttons_frame = ttk.Frame(action_frame)
        gen_buttons_frame.grid(row=0, column=0, padx=10, pady=5)
        
        ttk.Button(gen_buttons_frame, text="Generate 2D Mesh", command=self.generate_mesh2d, 
                   width=18, padding=8).grid(row=0, column=0, padx=8)
        ttk.Button(gen_buttons_frame, text="Generate 3D Mesh", command=self.generate_mesh3d, 
                   width=18, padding=8).grid(row=0, column=1, padx=8)
        
        export_frame = ttk.LabelFrame(bottom_frame, text=" Export ", labelanchor='nw')
        export_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        export_buttons = [
            ("OBJ (2D)", self.export_obj_2d),
            ("OBJ (3D)", self.export_obj_3d),
            ("STL (3D)", self.export_stl_3d)
        ]
        
        for i, (text, cmd) in enumerate(export_buttons):
            ttk.Button(export_frame, text=text, command=cmd, width=12, padding=6).grid(row=0, column=i, padx=6, pady=5)
        
        self.status_var = tk.StringVar(value="Ready - Load a font to begin")
        self.status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                                    relief='sunken', padding=6, font=('Segoe UI', 9))
        self.status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def browse_font(self):
        file_path = filedialog.askopenfilename(
            title="Select TTF Font File",
            filetypes=[("TrueType Fonts", "*.ttf"), ("All Files", "*.*")]
        )
        if file_path:
            self.font_path_var.set(file_path)
            self.load_font(file_path)
    
    def select_system_font(self):
        if not self.system_fonts:
            self.system_fonts = ttf_list_system_fonts()
            if not self.system_fonts:
                messagebox.showwarning("Warning", "No system fonts found")
                return
        
        font_names = [f"{f['name']} ({f['type']})" for f in self.system_fonts]
        font_names.sort()
        
        font_list = "\n".join(font_names[:30])
        if len(font_names) > 30:
            font_list += f"\n... and {len(font_names) - 30} more fonts"
        
        selected = simpledialog.askstring("Select Font", 
            f"Enter font name (partial match allowed):\n\n{font_list}")
        
        if selected:
            matched = ttf_match_font(self.system_fonts, family=selected)
            if matched:
                self.font_path_var.set(matched['path'])
                self.load_font(matched['path'])
            else:
                messagebox.showinfo("Info", "No matching font found")
    
    def load_font(self, file_path):
        try:
            result, font = ttf_load_from_file(file_path)
            if result == TTF_DONE:
                self.font = font
                family = font.names.get('family', 'Unknown')
                subfamily = font.names.get('subfamily', 'Regular')
                self.status_var.set(f"Loaded: {family} {subfamily} - {font.nchars} characters, {font.nglyphs} glyphs")
                self.update_info(f"Font: {family} {subfamily}\nCharacters: {font.nchars}\nGlyphs: {font.nglyphs}\n")
                self.update_preview()
            else:
                messagebox.showerror("Error", f"Failed to load font (error code: {result})")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load font: {str(e)}")
    
    def update_preview(self):
        if not self.font:
            messagebox.showwarning("Warning", "Please load a font first")
            return
        
        char = self.char_input_var.get()
        if not char:
            return
        
        char_code = ord(char[0])
        glyph_idx = ttf_find_glyph(self.font, char_code)
        
        if glyph_idx < 0 or glyph_idx >= self.font.nglyphs:
            messagebox.showwarning("Warning", f"Character '{char}' (U+{char_code:04X}) not found in font")
            return
        
        self.current_glyph = self.font.glyphs[glyph_idx]
        self.draw_glyph(self.current_glyph)
        self.update_glyph_info()
    
    def _calculate_signed_area(self, points):
        """Calculate signed area of contour. Positive = CW, Negative = CCW"""
        area = 0.0
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i+1)%n]
            area += (x1 * y2) - (x2 * y1)
        return area / 2.0
    
    def _extract_contours_with_curve_sampling(self, glyph, curve_steps=20):
        """Extract contours with bezier curve sampling (exact method from font2tri_lib.py)"""
        import numpy as np
        from fontTools.pens.basePen import BasePen
        from fontTools.ttLib import TTFont
        
        class ContourPen(BasePen):
            def __init__(self, glyphSet, curve_steps=20):
                super().__init__(glyphSet)
                self.contours = []
                self.current_contour = []
                self.curve_steps = curve_steps
            
            def _moveTo(self, pt):
                self.current_contour = [pt]
            
            def _lineTo(self, pt):
                self.current_contour.append(pt)
            
            def cubic_bezier(self, t, P0, P1, P2, P3):
                x = (1 - t) ** 3 * P0[0] + 3 * (1 - t) ** 2 * t * P1[0] + 3 * (1 - t) * t ** 2 * P2[0] + t ** 3 * P3[0]
                y = (1 - t) ** 3 * P0[1] + 3 * (1 - t) ** 2 * t * P1[1] + 3 * (1 - t) * t ** 2 * P2[1] + t ** 3 * P3[1]
                return (x, y)
            
            def _curveToOne(self, pt1, pt2, pt3):
                p0 = self.current_contour[-1]
                t_values = np.linspace(0, 1, self.curve_steps)
                curve_points = [self.cubic_bezier(t, p0, pt1, pt2, pt3) for t in t_values[1:]]
                self.current_contour.extend(curve_points)
            
            def quad_bezier(self, t, P0, P1, P2):
                x = (1-t)**2 * P0[0] + 2*(1-t)*t * P1[0] + t**2 * P2[0]
                y = (1-t)**2 * P0[1] + 2*(1-t)*t * P1[1] + t**2 * P2[1]
                return (x, y)
            
            def _qCurveToOne(self, pt1, pt2):
                p0 = self.current_contour[-1]
                t_values = np.linspace(0, 1, self.curve_steps)
                curve_points = [self.quad_bezier(t, p0, pt1, pt2) for t in t_values[1:]]
                self.current_contour.extend(curve_points)
            
            def _closePath(self):
                if len(self.current_contour) > 0:
                    self.contours.append(np.array(self.current_contour))
                    self.current_contour = []
        
        def close_contour(points):
            if len(points) < 3:
                return points
            if not np.allclose(points[0], points[-1], atol=1e-3):
                points = np.vstack([points, points[0]])
            return points
        
        font_path = self.font_path_var.get()
        if not font_path:
            return []
        
        ft = TTFont(font_path)
        glyphSet = ft.getGlyphSet()
        
        char_code = ord(self.char_input_var.get()[0]) if self.char_input_var.get() else ord('A')
        cmap = ft.getBestCmap()
        
        if char_code not in cmap:
            return []
        
        ft_glyph = glyphSet[cmap[char_code]]
        pen = ContourPen(glyphSet, curve_steps=curve_steps)
        ft_glyph.draw(pen)
        
        contours = []
        for contour in pen.contours:
            contours.append(close_contour(contour))
        
        result = []
        for contour in contours:
            result.append([(pt[0], pt[1]) for pt in contour])
        
        return result
    
    def draw_glyph(self, glyph):
        """Display glyph contours exactly as in font2tri_lib.py: outer contours red, inner contours blue"""
        self.preview_canvas.delete('all')
        
        font_path = r"C:\Windows\Fonts\simkai.ttf"
        if not os.path.exists(font_path):
            font_path = self.font_path_var.get()
        
        if not font_path or not os.path.exists(font_path):
            return
        
        from ttf2mesh.font2tri_lib import FontTriangulator, contour_area
        
        triangulator = FontTriangulator(font_path)
        char = self.char_input_var.get()[0] if self.char_input_var.get() else 'A'
        contours = triangulator.extract_sampled_contours(char, curve_steps=20)
        
        if not contours:
            return
        
        all_points = []
        for contour in contours:
            for pt in contour:
                all_points.append(pt)
        
        xs = [x for x, y in all_points]
        ys = [y for x, y in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        glyph_width = max_x - min_x
        glyph_height = max_y - min_y
        
        if glyph_width < EPSILON or glyph_height < EPSILON:
            return
        
        canvas_width = self.preview_canvas.winfo_width() - 10
        canvas_height = self.preview_canvas.winfo_height() - 10
        
        if canvas_width < 50 or canvas_height < 50:
            canvas_width = 260
            canvas_height = 260
        
        scale = min(canvas_width / glyph_width, canvas_height / glyph_height) * 0.9
        offset_x = canvas_width // 2
        offset_y = canvas_height // 2
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        self.preview_canvas.create_rectangle(0, 0, canvas_width, canvas_height, fill='white', outline='')
        
        for contour in contours:
            if len(contour) < 3:
                continue
            
            area = contour_area(contour)
            
            transformed = []
            for x, y in contour:
                tx = (x - center_x) * scale + offset_x
                ty = canvas_height - ((y - center_y) * scale + offset_y)
                transformed.append((tx, ty))
            
            color = 'red' if area < 0 else 'blue'
            
            self.preview_canvas.create_line(transformed + [transformed[0]], fill=color, width=2, smooth=False)
        
        self.preview_canvas.create_rectangle(
            (min_x - center_x) * scale + offset_x,
            canvas_height - ((min_y - center_y) * scale + offset_y),
            (max_x - center_x) * scale + offset_x,
            canvas_height - ((max_y - center_y) * scale + offset_y),
            outline='gray', dash=(2, 2)
        )
        
        self.preview_canvas.create_text(canvas_width // 2, canvas_height - 5, 
                                       text=f"U+{ord(self.char_input_var.get()[0]):04X}", 
                                       anchor=tk.S, font=('Segoe UI', 9), fill='#666')
    
    def update_glyph_info(self):
        if not self.current_glyph:
            return
        
        glyph = self.current_glyph
        info = f"Glyph Index: {glyph.index}\n"
        info += f"Bounds: X[{glyph.xbounds[0]:.2f}, {glyph.xbounds[1]:.2f}] "
        info += f"Y[{glyph.ybounds[0]:.2f}, {glyph.ybounds[1]:.2f}]\n"
        
        if glyph.outline:
            contours = len(glyph.outline.contours)
            total_points = sum(len(c.points) for c in glyph.outline.contours)
            info += f"Contours: {contours}\nPoints: {total_points}\n"
        
        self.update_info(info)
    
    def update_info(self, info):
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info)
        self.info_text.config(state='disabled')
    
    def generate_mesh2d(self):
        if not self.current_glyph:
            messagebox.showwarning("Warning", "Please select a character first")
            return
        
        try:
            quality_name = self.quality_combo.get()
            quality = self.quality_map.get(quality_name, TTF_QUALITY_NORMAL)
            self.mesh2d = ttf_glyph2mesh(self.current_glyph, quality=quality)
            self.mesh3d = None
            
            if self.mesh2d:
                info = f"2D Mesh Generated:\n"
                info += f"Vertices: {self.mesh2d.nvert}\n"
                info += f"Faces: {self.mesh2d.nfaces}\n"
                self.update_info(info)
                self.status_var.set(f"2D Mesh: {self.mesh2d.nvert} vertices, {self.mesh2d.nfaces} faces")
                self.draw_mesh_preview()
            else:
                messagebox.showerror("Error", "Failed to generate 2D mesh")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate mesh: {str(e)}")
    
    def generate_mesh3d(self):
        if not self.current_glyph:
            messagebox.showwarning("Warning", "Please select a character first")
            return
        
        try:
            quality_name = self.quality_combo.get()
            quality = self.quality_map.get(quality_name, TTF_QUALITY_NORMAL)
            features = TTF_FEATURE_GEN_NORMALS
            self.mesh3d = ttf_glyph2mesh3d(
                self.current_glyph,
                quality=quality,
                features=features,
                depth=self.depth_var.get()
            )
            self.mesh2d = None
            
            if self.mesh3d:
                info = f"3D Mesh Generated:\n"
                info += f"Vertices: {self.mesh3d.nvert}\n"
                info += f"Faces: {self.mesh3d.nfaces}\n"
                info += f"Depth: {self.depth_var.get()}\n"
                info += f"Normals: {len(self.mesh3d.normals) if self.mesh3d.normals else 0}\n"
                self.update_info(info)
                self.status_var.set(f"3D Mesh: {self.mesh3d.nvert} vertices, {self.mesh3d.nfaces} faces")
                self.draw_mesh_preview()
            else:
                messagebox.showerror("Error", "Failed to generate 3D mesh")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate mesh: {str(e)}")
    
    def draw_mesh_preview(self):
        """Draw mesh preview on canvas"""
        self.mesh_canvas.delete('all')
        
        mesh = self.mesh3d if self.mesh3d else self.mesh2d
        if not mesh:
            self.mesh_canvas.create_text(140, 140, text="Generate a mesh\nto preview", 
                                        fill='#999', font=('Arial', 12), justify='center')
            return
        
        canvas_width = self.mesh_canvas.winfo_width() - 10
        canvas_height = self.mesh_canvas.winfo_height() - 10
        
        if canvas_width < 50 or canvas_height < 50:
            canvas_width = 260
            canvas_height = 260
        
        xs = [v[0] for v in mesh.vert]
        ys = [v[1] for v in mesh.vert]
        
        if self.mesh3d:
            zs = [v[2] for v in mesh.vert]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        width = max_x - min_x
        height = max_y - min_y
        
        if width < EPSILON or height < EPSILON:
            return
        
        scale = min(canvas_width / width, canvas_height / height) * 0.9
        offset_x = canvas_width // 2
        offset_y = canvas_height // 2
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        view_mode = self.view_mode_var.get()
        
        is_2d = len(mesh.vert[0]) == 2 if mesh.vert else True
        
        if is_2d:
            if view_mode == 'solid':
                for face in mesh.faces:
                    v0 = mesh.vert[face[0]]
                    v1 = mesh.vert[face[1]]
                    v2 = mesh.vert[face[2]]
                    
                    x0 = (v0[0] - center_x) * scale + offset_x
                    y0 = -(v0[1] - center_y) * scale + offset_y
                    x1 = (v1[0] - center_x) * scale + offset_x
                    y1 = -(v1[1] - center_y) * scale + offset_y
                    x2 = (v2[0] - center_x) * scale + offset_x
                    y2 = -(v2[1] - center_y) * scale + offset_y
                    
                    self.mesh_canvas.create_polygon(x0, y0, x1, y1, x2, y2, 
                                                   fill='#5a9bd4', outline='#2c5282', width=0.5)
            else:
                edges = set()
                for face in mesh.faces:
                    for i in range(3):
                        v1 = face[i]
                        v2 = face[(i+1)%3]
                        edge = tuple(sorted([v1, v2]))
                        edges.add(edge)
                
                for v1, v2 in edges:
                    x1 = (mesh.vert[v1][0] - center_x) * scale + offset_x
                    y1 = -(mesh.vert[v1][1] - center_y) * scale + offset_y
                    x2 = (mesh.vert[v2][0] - center_x) * scale + offset_x
                    y2 = -(mesh.vert[v2][1] - center_y) * scale + offset_y
                    
                    self.mesh_canvas.create_line(x1, y1, x2, y2, fill='#2c5282', width=1)
        else:
            self.viewer3d.render(mesh, self.mesh_canvas, canvas_width, canvas_height, view_mode)
    
    def redraw_mesh_preview(self):
        """Redraw mesh preview when view mode changes"""
        self.draw_mesh_preview()
    
    def on_mouse_down(self, event):
        """Handle mouse down event for 3D rotation"""
        if self.mesh3d:
            self.dragging = True
            self.last_x = event.x
            self.last_y = event.y
    
    def on_mouse_drag(self, event):
        """Handle mouse drag event for 3D rotation"""
        if self.dragging and self.mesh3d:
            dx = event.x - self.last_x
            dy = event.y - self.last_y
            
            self.viewer3d.rotate(dx, dy)
            self.draw_mesh_preview()
            
            self.last_x = event.x
            self.last_y = event.y
    
    def on_mouse_up(self, event):
        """Handle mouse up event"""
        self.dragging = False
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel event for zooming"""
        if self.mesh3d:
            # Windows uses delta, Linux uses num
            if hasattr(event, 'delta'):
                delta = event.delta / 120  # Normalize to -1 or 1
            else:
                delta = 1 if event.num == 4 else -1  # Linux
            
            self.viewer3d.zoom(delta)
            self.draw_mesh_preview()
            
            # Prevent default scroll behavior
            return 'break'
    
    def reset_view(self):
        """Reset 3D view to default position"""
        if self.mesh3d:
            self.viewer3d.set_rotation(30.0, 45.0, 0.0)
            self.viewer3d.camera_distance = 0.5  # Further reduced for larger display
            self.draw_mesh_preview()
            self.status_var.set("View reset to default")
    
    def set_view_preset(self, preset):
        """Set view to preset angle"""
        if self.mesh3d:
            presets = {
                'front': (0, 0, 0),
                'back': (0, 180, 0),
                'left': (0, -90, 0),
                'right': (0, 90, 0),
                'top': (-90, 0, 0),
                'bottom': (90, 0, 0),
                'isometric': (30, 45, 0)
            }
            if preset in presets:
                self.viewer3d.set_rotation(*presets[preset])
                self.draw_mesh_preview()
                self.status_var.set(f"View: {preset}")
    
    def export_obj_2d(self):
        if not self.mesh2d:
            self.generate_mesh2d()
        
        if self.mesh2d:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".obj",
                filetypes=[("Wavefront OBJ", "*.obj"), ("All Files", "*.*")]
            )
            if file_path:
                if mesh_to_obj(self.mesh2d, file_path):
                    messagebox.showinfo("Success", "2D mesh exported successfully!")
                    self.status_var.set(f"Exported: {os.path.basename(file_path)}")
                else:
                    messagebox.showerror("Error", "Failed to export")
    
    def export_obj_3d(self):
        if not self.mesh3d:
            self.generate_mesh3d()
        
        if self.mesh3d:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".obj",
                filetypes=[("Wavefront OBJ", "*.obj"), ("All Files", "*.*")]
            )
            if file_path:
                if mesh3d_to_obj(self.mesh3d, file_path):
                    messagebox.showinfo("Success", "3D mesh exported successfully!")
                    self.status_var.set(f"Exported: {os.path.basename(file_path)}")
                else:
                    messagebox.showerror("Error", "Failed to export")
    
    def export_stl_3d(self):
        if not self.mesh3d:
            self.generate_mesh3d()
        
        if self.mesh3d:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".stl",
                filetypes=[("STL File", "*.stl"), ("All Files", "*.*")]
            )
            if file_path:
                if mesh3d_to_stl(self.mesh3d, file_path):
                    messagebox.showinfo("Success", "STL file exported successfully!")
                    self.status_var.set(f"Exported: {os.path.basename(file_path)}")
                else:
                    messagebox.showerror("Error", "Failed to export")
    
    def show_about(self):
        about_text = """TTFMeshForge GUI v1.0

A graphical interface for converting TrueType font glyphs to 2D/3D meshes.

Features:
- Load TTF fonts from file or system
- Preview glyph outlines with color-coded contours
- Generate 2D triangular meshes with adjustable quality
- Generate 3D extruded meshes with configurable depth
- Interactive 3D mesh viewing (rotate, zoom)
- Export to OBJ and STL formats"""
        
        messagebox.showinfo("About TTFMeshForge", about_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = TTFFontViewer(root)
    root.mainloop()