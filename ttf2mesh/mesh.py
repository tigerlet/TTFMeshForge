import math
import struct
from .core import *
from .mesher import *


def mesh3d_extrude(mesh2d, depth, features=0):
    """Extrude 2D mesh to 3D with proper side walls"""
    if mesh2d is None:
        return None

    mesh3d = TTFTriMesh3D()

    # Create top and bottom vertices
    for v in mesh2d.vert:
        mesh3d.vert.append((v[0], v[1], depth / 2.0))
        mesh3d.vert.append((v[0], v[1], -depth / 2.0))

    mesh3d.nvert = len(mesh3d.vert)

    # Create top faces (same orientation as 2D)
    for face in mesh2d.faces:
        v0 = face[0] * 2
        v1 = face[1] * 2
        v2 = face[2] * 2
        mesh3d.faces.append([v0, v1, v2])

    # Create bottom faces (reversed orientation)
    for face in mesh2d.faces:
        v0 = face[0] * 2 + 1
        v1 = face[2] * 2 + 1
        v2 = face[1] * 2 + 1
        mesh3d.faces.append([v0, v1, v2])

    # Find boundary edges of the 2D mesh
    boundary_edges = set()
    for face in mesh2d.faces:
        for i in range(3):
            v1 = face[i]
            v2 = face[(i + 1) % 3]
            edge = tuple(sorted([v1, v2]))
            if edge in boundary_edges:
                boundary_edges.remove(edge)
            else:
                boundary_edges.add(edge)

    # Create side faces for each boundary edge
    for v1, v2 in boundary_edges:
        mesh3d.faces.append([v1 * 2, v2 * 2, v1 * 2 + 1])
        mesh3d.faces.append([v2 * 2, v2 * 2 + 1, v1 * 2 + 1])

    mesh3d.nfaces = len(mesh3d.faces)

    # Generate normals if requested
    if features & TTF_FEATURE_GEN_NORMALS:
        mesh3d.normals = [(0.0, 0.0, 0.0) for _ in range(mesh3d.nvert)]

        for face in mesh3d.faces:
            v0, v1, v2 = face
            p0 = mesh3d.vert[v0]
            p1 = mesh3d.vert[v1]
            p2 = mesh3d.vert[v2]

            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]

            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx

            mesh3d.normals[v0] = (mesh3d.normals[v0][0] + nx,
                                  mesh3d.normals[v0][1] + ny,
                                  mesh3d.normals[v0][2] + nz)
            mesh3d.normals[v1] = (mesh3d.normals[v1][0] + nx,
                                  mesh3d.normals[v1][1] + ny,
                                  mesh3d.normals[v1][2] + nz)
            mesh3d.normals[v2] = (mesh3d.normals[v2][0] + nx,
                                  mesh3d.normals[v2][1] + ny,
                                  mesh3d.normals[v2][2] + nz)

        for i in range(mesh3d.nvert):
            nx, ny, nz = mesh3d.normals[i]
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length > 1e-6:
                mesh3d.normals[i] = (nx / length, ny / length, nz / length)

    return mesh3d


def ttf_glyph2mesh3d(glyph, quality=TTF_QUALITY_NORMAL, features=0, depth=0.1):
    """Convert glyph to 3D mesh"""
    mesh2d = ttf_glyph2mesh(glyph, quality, features)
    if mesh2d is None:
        return None

    return mesh3d_extrude(mesh2d, depth, features)


def mesh3d_to_obj(mesh3d, filename):
    """Export 3D mesh to Wavefront OBJ format"""
    if mesh3d is None:
        return False

    try:
        with open(filename, 'w') as f:
            for v in mesh3d.vert:
                f.write(f'v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n')

            if mesh3d.normals:
                for n in mesh3d.normals:
                    f.write(f'vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n')

            for face in mesh3d.faces:
                if mesh3d.normals:
                    f.write(f'f {face[0]+1}//{face[0]+1} {face[1]+1}//{face[1]+1} {face[2]+1}//{face[2]+1}\n')
                else:
                    f.write(f'f {face[0]+1} {face[1]+1} {face[2]+1}\n')

        return True
    except:
        return False


def mesh3d_to_stl(mesh3d, filename):
    """Export 3D mesh to STL format"""
    if mesh3d is None:
        return False

    try:
        with open(filename, 'wb') as f:
            # STL header
            f.write(b' ' * 80)

            # Number of triangles
            f.write(struct.pack('<I', mesh3d.nfaces))

            for face in mesh3d.faces:
                p0 = mesh3d.vert[face[0]]
                p1 = mesh3d.vert[face[1]]
                p2 = mesh3d.vert[face[2]]

                if mesh3d.normals:
                    n = mesh3d.normals[face[0]]
                else:
                    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
                    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
                    n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
                    length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
                    if length > 1e-6:
                        n = (n[0] / length, n[1] / length, n[2] / length)
                    else:
                        n = (0.0, 0.0, 1.0)

                f.write(struct.pack('<fff', *n))
                f.write(struct.pack('<fff', *p0))
                f.write(struct.pack('<fff', *p1))
                f.write(struct.pack('<fff', *p2))
                f.write(struct.pack('<H', 0))

        return True
    except:
        return False