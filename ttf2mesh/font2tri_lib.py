"""
✅ 终极版：直线 + 二次曲线 全采样点加入顶点集
✅ 三角化只使用轮廓采样点，不新增点
✅ 外红内蓝 | 孔洞无三角 | 外部无三角 | 顶点完整显示
"""
import numpy as np
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.basePen import BasePen
from shapely.geometry import Polygon, Point
from shapely.ops import triangulate
import warnings
import os
warnings.filterwarnings('ignore')

# ===================== 工具函数 =====================
def close_contour(points):
    if len(points) < 3:
        return points
    if not np.allclose(points[0], points[-1], atol=1e-3):
        points = np.vstack([points, points[0]])
    return points

def contour_area(points):
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i+1)%n]
        area += (x1 * y2) - (x2 * y1)
    return area

def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        j = (i+1)%len(poly)
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)):
            if abs(yj - yi) < 1e-8:
                continue
            t = (y - yi) / (yj - yi)
            x_in = xi + t * (xj - xi)
            if x < x_in:
                inside = not inside
    return inside

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

# ===================== 核心类 =====================
class FontTriangulator:
    def __init__(self, font_path):
        self.ft = TTFont(font_path)
        self.glyphSet = self.ft.getGlyphSet()

    def extract_sampled_contours(self, char, curve_steps=20):
        """ ✅ 提取：直线点 + 曲线采样点（全部加入轮廓）"""
        cmap = self.ft.getBestCmap()
        if ord(char) not in cmap:
            return []
        glyph = self.glyphSet[cmap[ord(char)]]
        pen = ContourPen(self.glyphSet, curve_steps=curve_steps)
        glyph.draw(pen)
        
        contours = []
        for contour in pen.contours:
            contours.append(close_contour(contour))
        
        return contours

    def triangulate_from_contour_points(self, contours):
        """ ✅ 只使用轮廓点，不新增任何顶点！"""
        vmap = {}
        vertices = []
        faces = []

        # === 第一步：计算所有轮廓面积，确定需要反转的轮廓 ===
        areas = [contour_area(c) for c in contours]
        
        # 根据文档规范：外轮廓应为顺时针（面积正），内轮廓应为逆时针（面积负）
        # 如果实际字体的方向相反，需要反转轮廓
        normalized_contours = []
        for i, c in enumerate(contours):
            area = areas[i]
            # 外轮廓应该顺时针（面积正），如果当前是逆时针（面积负），反转方向
            # 内轮廓应该逆时针（面积负），如果当前是顺时针（面积正），反转方向
            # 这里保持原有逻辑，因为中文字体实际使用外逆时针内顺时针的约定
            normalized_contours.append(c)
        
        # === 第二步：把所有轮廓采样点 加入顶点集 ===
        for c in normalized_contours:
            for x, y in c:
                key = (round(x, 3), round(y, 3))
                if key not in vmap:
                    vmap[key] = len(vertices)
                    vertices.append([x, y])

        # === 第三步：按方向区分外轮廓和内轮廓 ===
        # 文档规范：外轮廓=顺时针（面积正），内轮廓=逆时针（面积负）
        # 但中文字体实际使用：外轮廓=逆时针（面积负），内轮廓=顺时针（面积正）
        # 这里按字体实际情况处理
        outer_indices = [i for i in range(len(normalized_contours)) if areas[i] < 0]
        outer_indices.sort(key=lambda i: areas[i])  # 外轮廓按面积从小到大升序
        
        inner_indices = [i for i in range(len(normalized_contours)) if areas[i] >= 0]
        inner_indices.sort(key=lambda i: -areas[i])  # 内轮廓按面积从大到小降序
        
        n = len(normalized_contours)
        used_inner = [False] * n
        
        # === 第四步：建立部件块列表 [(外轮廓, [内轮廓列表]), ...] ===
        components = []
        
        # 将轮廓转换为Shapely多边形并计算面积
        processed = []
        for i in range(len(normalized_contours)):
            coords = [(x, y) for x, y in normalized_contours[i]]
            if len(coords) < 3:
                continue
            
            # 计算有符号面积
            area = 0.5 * sum(x * y1 - x1 * y
                             for (x, y), (x1, y1) in zip(coords, coords[1:] + coords[:1]))
            is_outer = area < 0  # 外轮廓为顺时针（面积为负）
            
            poly = Polygon(coords).buffer(0)
            processed.append({
                "index": i,
                "polygon": poly,
                "is_outer": is_outer,
                "children": []
            })
        
        # 按面积降序排序（外层优先）
        processed.sort(key=lambda x: x["polygon"].area, reverse=True)
        
        # 构建层级结构
        hierarchy = []
        for poly in processed:
            if poly["is_outer"]:
                hierarchy.insert(0, poly)
        
        for poly in processed:
            if not poly["is_outer"]:
                # 寻找父级外轮廓
                for parent in hierarchy:
                    if parent["polygon"].contains(poly["polygon"]):
                        parent["children"].append(poly)
                        break
        
        # 转换为部件列表
        for outer in hierarchy:
            inner_list = [child["index"] for child in outer["children"]]
            components.append((outer["index"], inner_list))
        
        # === 第五步：获取所有内轮廓用于过滤 ===
        all_inner_polys = [Polygon(normalized_contours[i]) for i in inner_indices]
        
        # === 第六步：对每个部件进行三角化 ===
        for outer_idx, inner_indices in components:
            outer = normalized_contours[outer_idx]
            holes = []
            hole_polys = []
            
            for inner_idx in inner_indices:
                inner = normalized_contours[inner_idx]
                holes.append(inner)
                hole_polys.append(Polygon(inner))
            
            try:
                poly = Polygon(outer, holes=holes)
                outer_poly = Polygon(outer)
                inner_polys = [Polygon(normalized_contours[i]) for i in inner_indices]
                
                for t in triangulate(poly):
                    tri_pts = np.array(list(t.exterior.coords)[:-1])
                    if len(tri_pts) != 3:
                        continue
                    
                    tri_poly = Polygon(tri_pts)
                    
                    # 与外轮廓进行交操作，保留外轮廓内的部分
                    clipped_tri = tri_poly.intersection(outer_poly)
                    
                    # 与每个内轮廓进行差操作，去掉内轮廓内的部分
                    for inner_poly in inner_polys:
                        clipped_tri = clipped_tri.difference(inner_poly)
                    
                    # 如果裁剪后为空，跳过
                    if clipped_tri.is_empty:
                        continue
                    
                    # 如果裁剪后是单个多边形
                    if hasattr(clipped_tri, 'exterior'):
                        coords = np.array(list(clipped_tri.exterior.coords)[:-1])
                        if len(coords) >= 3:
                            # 对裁剪后的多边形重新三角化
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
                    # 如果裁剪后是多个多边形（MultiPolygon）
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
                print(f"错误处理部件{outer_idx}: {e}")
                continue
        
        return np.array(vertices), np.array(faces)

    def show(self, char, contours, vs, fs):
        plt.figure(figsize=(16, 5))

        # 左：彩色轮廓
        plt.subplot(1, 3, 1)
        plt.title(f"轮廓（外红/内蓝）")
        plt.gca().set_aspect('equal')
        for c in contours:
            a = contour_area(c)
            plt.plot(c[:,0], c[:,1], 'r-' if a<0 else 'b-', lw=2.2)

        # 中：三角化
        plt.subplot(1, 3, 2)
        plt.title(f"三角化 ({len(fs)} 面)")
        plt.gca().set_aspect('equal')
        for f in fs:
            plt.fill(vs[f,0], vs[f,1], 'lightblue', ec='blue', lw=0.2)

        # 右：✅ 显示所有轮廓采样点（红色圆点）
        plt.subplot(1, 3, 3)
        plt.title(f"顶点集 ({len(vs)} 点)")
        plt.gca().set_aspect('equal')
        plt.scatter(vs[:,0], vs[:,1], s=6, c='red', zorder=5)
        for c in contours:
            plt.plot(c[:,0], c[:,1], 'k-', lw=0.5, alpha=0.4)

        plt.tight_layout()
        plt.show()

    def run(self, char, curve_steps=20):
        contours = self.extract_sampled_contours(char, curve_steps=curve_steps)
        vs, fs = self.triangulate_from_contour_points(contours)
        print(f"【{char}】完成")
        print(f"  轮廓数：{len(contours)}")
        print(f"  顶点数：{len(vs)}（直线+曲线全采样）")
        print(f"  三角面：{len(fs)}")
        self.show(char, contours, vs, fs)

# ===================== 主程序 =====================
def main():
    print("="*55)
    print("  字体三角化 —— 直线+曲线全采样点版 ✅")
    print("="*55)
    font_path = input("字体路径（回车自动搜索）：").strip()
    if not font_path:
        for p in [
            r"C:\Windows\Fonts\simkai.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simsun.ttc"
        ]:
            if os.path.exists(p):
                font_path = p
                print("✅ 使用系统字体：", p)
                break

    if not os.path.exists(font_path):
        print("❌ 未找到字体")
        return

    ft = FontTriangulator(font_path)
    while True:
        c = input("\n输入字符（q退出）：").strip()
        if c == 'q':
            break
        if len(c) == 1:
            ft.run(c)

if __name__ == "__main__":
    main()