from PyQt5.QtGui import (
        QImage,
        QMatrix4x4,
        QOffscreenSurface,
        QOpenGLContext,
        QPixmap,
        QSurfaceFormat,
        QTransform,
        QVector2D,
        QVector3D,
        QVector4D,
        )

# from PySide6.QtOpenGL import (
from PyQt5.QtGui import (
        QOpenGLVertexArrayObject,
        QOpenGLBuffer,
        QOpenGLDebugLogger,
        QOpenGLDebugMessage,
        QOpenGLFramebufferObject,
        QOpenGLFramebufferObjectFormat,
        QOpenGLShader,
        QOpenGLShaderProgram,
        QOpenGLTexture,
        )

from PyQt5.QtWidgets import (
        QApplication, 
        QGridLayout,
        QHBoxLayout,
        QMainWindow,
        QWidget,
        )

# from PySide6.QtOpenGLWidgets import (
from PyQt5.QtWidgets import (
        QOpenGLWidget,
        )

from PyQt5.QtCore import (
        QFileInfo,
        QPointF,
        QSize,
        QTimer,
        )

import time
from collections import OrderedDict
import numpy as np
import cv2
from OpenGL import GL as pygl
# from shiboken6 import VoidPtr
import ctypes
def VoidPtr(i):
    return ctypes.c_void_p(i)

from utils import Utils
from data_window import DataWindow
from gl_data_window import GLDataWindowChild


class GLSurfaceWindow(DataWindow):
    def __init__(self, window):
        super(GLSurfaceWindow, self).__init__(window, 2)
        # self.clear()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)
        self.glw = GLSurfaceWindowChild(self)
        layout.addWidget(self.glw)
        # self.zoomMult = .5
        self.zoomMult = 2

    # see comments for this function in DataWindow
    def nodeMovementAllowedInK(self):
        return True

    def allowMouseToDragNode(self):
        return False

    '''
    def setIjkTf(self, tf):
        oijk = self.volume_view.ijktf
        iind = self.iIndex
        jind = self.jIndex
        kind = self.kIndex
        di = tf[iind] - oijk[iind]
        dj = tf[jind] - oijk[jind]
        zoom = self.getZoom()
        dx = di*zoom
        dy = dj*zoom
        ww, wh = self.width(), self.height()
        ox, oy = ww/2, wh/2
        nx, ny = ox+dx, oy+dy
        nijk = self.xyToTijk((nx,ny))
        self.volume_view.setIjkTf(nijk)
        ostxy = self.volume_view.stxytf
        nstxy = (ostxy[0]+di, ostxy[1]+dj)

        self.volume_view.setStxyTf(nstxy)
    '''

    '''
    def shiftIjk(self, di, dj, dk):
        oxy = self.volume_view.stxytf
        nxy = (oxy[0]+di, oxy[1]+dj)
        zoom = self.getZoom()
        dx = di*zoom
        dy = dj*zoom
        ww, wh = self.width(), self.height()
        ox, oy = ww/2, wh/2
        nx, ny = ox+dx, oy+dy
        nijk = self.xyToTijk((nx,ny))
        self.volume_view.setIjkTf(nijk)
        self.volume_view.setStxyTf(nxy)
    '''

    def setIjkTf(self, tf):
        ij = self.tijkToIj(tf)
        '''
        xy = self.ijToXy(ij)
        d = 10
        xyl = (xy[0]-d, xy[1]-d)
        xyg = (xy[0]+d, xy[1]+d)

        stxy = self.stxyInBounds(xyl, xyg, tf)
        '''
        stxy = self.ijkToStxy(tf)
        # print("tf, xy, stxy", tf, xy, stxy)
        if stxy is not None:
            self.volume_view.setStxyTf(stxy)
        self.volume_view.setIjkTf(tf)

    def computeTfStartPoint(self):
        stxy = self.volume_view.stxytf
        if stxy is None:
            return None
        return (stxy[0], stxy[1], 0)
        # print("tfs", len(tfs), tfs)
        # return tfs

    # def setTf(self, tf):
    #     self.setIjkOrStxyTf(tf)

    def setTf(self, tf):
        tf = tf[:2]
        ostxy = self.volume_view.stxytf
        iind = self.iIndex
        jind = self.jIndex
        kind = self.kIndex
        di = tf[iind]-ostxy[iind]
        dj = tf[jind]-ostxy[jind]
        zoom = self.getZoom()
        dx = di*zoom
        dy = dj*zoom
        ww, wh = self.width(), self.height()
        ox, oy = ww/2, wh/2
        nx, ny = ox+dx, oy+dy
        nijk = self.xyToTijk((nx,ny))
        self.volume_view.setIjkTf(nijk)
        self.volume_view.setStxyTf(tf)

    def ijkToStxy(self, ijk):
        xyz_arr = self.glw.xyz_arr
        if xyz_arr is None:
            return None
        dxyz = (xyz_arr[:,:,:3] - ijk).astype(np.float32)
        dxyz *= dxyz
        dsq = dxyz.sum(axis=2)
        dsq[xyz_arr[:,:,3] == 0] = 2**30
        minindex = np.unravel_index(dsq.argmin(), dsq.shape)
        # print("shapes", xyz_arr.shape, dsq.shape)
        # print("minindex", minindex, xyz_arr[*minindex,:3], ijk)
        iy,ix = minindex
        zoom = self.getZoom()
        ratio = self.screen().devicePixelRatio()
        x = ix/ratio
        y = iy/ratio
        w = self.width()
        h = self.height()
        hw = w/2
        hh = h/2
        dx = (x-hw)/zoom
        dy = (y-hh)/zoom
        ostxy = self.volume_view.stxytf
        nstxy = (ostxy[0]+dx, ostxy[1]+dy)
        return nstxy

    def xyToTijk(self, xy):
        x, y = xy
        iind = self.iIndex
        jind = self.jIndex
        kind = self.kIndex
        xyz_arr = self.glw.xyz_arr
        if xyz_arr is None:
            # print("xyz_arr is None; returning vv.ijktf")
            # return None
            return self.volume_view.ijktf
        ratio = self.screen().devicePixelRatio()
        ix = round(x*ratio)
        iy = round(y*ratio)
        if iy < 0 or iy >= xyz_arr.shape[0] or ix < 0 or ix >= xyz_arr.shape[1]:
            print("error", x, y, xyz_arr.shape)
            return self.volume_view.ijktf
        xyza = xyz_arr[iy, ix]
        if xyza[3] == 0:
            return self.volume_view.ijktf
        i = xyza[iind]
        j = xyza[jind]
        k = xyza[kind]
        return (i,j,k)

    def ijToTijk(self, ij):
        return (ij[0], ij[1], 0)

    def getTrackingCursorXy(self):
        stxyz = self.window.cursor_stxyz
        # print("gtxy", stxyz)
        if stxyz is None:
            return None
        xy = self.stxyToWindowXy(stxyz[:2])
        # print("gtxy", xy)
        return xy

    def getTrackingCursorHeight(self):
        stxyz = self.window.cursor_stxyz
        if stxyz is None:
            return None
        # print("gth", stxyz[2])
        return stxyz[2]

    def stxyToWindowXy(self, ij):
        zoom = self.getZoom()
        cij = self.volume_view.stxytf
        if cij is None:
            return None
        ci = cij[0]
        cj = cij[1]
        ww, wh = self.width(), self.height()
        wcx, wcy = ww//2, wh//2
        # cij = np.array(cij)
        # wc = np.array((wcx,wcy))
        # xys = np.rint(zoom*(ijs-cij)+wc).astype(np.int32)

        # note that the values are floats:
        xy = (wcx+zoom*(ij[0]-ci), wcy+zoom*(ij[1]-cj))
        return xy

    def getXyzsInRange(self, stxy, stxy_radius):
        # From all the pixels in the window, keep only those
        # whose stxy is in range.
        # Then get the xyz points from these pixels.
        # Or less accurately, get all the xyz points from all 
        # the pixels in the window, and keep those 
        # within the radius.
        pass

    '''
    # NOTE: not debugged or tested
    # returns a 2D array.  Columns: scroll xyz, stxy, window xy
    def getXyzGrid(self):
        xyz_arr = self.glw.xyz_arr
        if xyz_arr is None:
            return None
        zoom = self.getZoom()
        ratio = self.screen().devicePixelRatio()
        stxy_center = self.volume_view.stxytf
        # TODO: ww, wh should be based on size of xyz_arr
        # ww, wh = int(ratio*self.width()), int(ratio*self.height())
        # wcx, wcy = ww//2, wh//2
        window_center = (xyz_arr.shape[1]//2, xyz_arr.shape[0]//2)

        # print("xyz_arr", xyz_arr.shape, xyz_arr.dtype)
        wxys = np.array(np.nonzero(xyz_arr[:,:,3] != 0)).T
        # print("wxys", wxys.shape, wxys.dtype)
        stxys = stxy_center+(wxys-window_center)/(ratio*zoom)
        # print("stxys", stxys.shape, stxys.dtype)
        scrxyzs = xyz_arr[wxys[:,0], wxys[:,1], :3]
        # print("scrxyzs", scrxyzs.shape, scrxyzs.dtype)
        # TODO: should wxys be OpenGL window coords or Qt coords?
        xyzgrid = np.concatenate((scrxyzs, stxys, wxys), axis=1)
        # print("xyzgrid", xyzgrid.shape, xyzgrid.dtype)
        return xyzgrid
    '''

    def setNearbyNodeIjk(self, ijk):
        # print("snnijk", ijk)
        stxys = self.cur_frag_pts_stxy
        xyijks = self.cur_frag_pts_xyijk
        nearbyNode = self.localNearbyNodeIndex
        if nearbyNode < 0 or stxys.shape[0] == 0:
            return
        stxy = stxys[nearbyNode, 0:2]
        oijk = xyijks[nearbyNode, 2:5]
        dijk = ijk-oijk
        # Use convention that ^ is outwards
        dijk[2] *= -1
        index = int(stxys[nearbyNode, 2])
        # wxy = xyijks[nearbyNode, 0:2]
        # print(" ", index, oijk, dijk, stxy)
        # print(" oijk", oijk, self.getNearbyNodeIjk())
        # print(" dijk", dijk)
        # size of data window to use, in units of stxy
        # window_half_width = 20
        # xyzg = self.getXyzGrid()
        fv = self.glw.active_vao.fragment_view
        # normal = fv.pointNormal(index)
        axes = fv.fragment.pointThreeAxes(index, fv.fpoints[:,:3], fv.stpoints, fv.trgls())
        # print(" ", axes)
        # nijk = oijk + dijk[0]*axes[0]+dijk[1]*axes[1]+dijk[2]*axes[2]
        if axes is None:
            print("GLSurfaceWindow.setNearbyNodeIjk: could not compute axes")
            return
        nijk = oijk + axes@dijk
        # print(" nijk", nijk)
        super(GLSurfaceWindow, self).setNearbyNodeIjk(nijk.tolist())

    def stxyWindowBounds(self):
        stxy = self.volume_view.stxytf
        if stxy is None:
            return ((0.,0.), (-1.,-1.))
        zoom = self.getZoom()
        ww, wh = self.width(), self.height()
        hw, hh = ww/2, wh/2
        dx,dy = hw/zoom, hh/zoom
        return ((stxy[0]-dx,stxy[1]-dy),(stxy[0]+dx,stxy[1]+dy))

    def drawSlice(self):
        # the MainWindow.edit widget overlays the
        # fragment map; it was used for displaying 
        # user documentation when khartes would first 
        # start up.  We don't want it to block the gl window.
        self.window.edit.hide()
        self.window.setFocus()
        self.glw.update()

slice_code = {
    "name": "slice",

    "vertex": '''
      #version 410 core

      in vec2 position;
      in vec2 vtxt;
      out vec2 ftxt;
      void main() {
        gl_Position = vec4(position, 0.0, 1.0);
        ftxt = vtxt;
      }
    ''',

    "fragment": '''
      #version 410 core

      uniform sampler2D base_sampler;
      uniform sampler2D underlay_sampler;
      uniform sampler2D overlay_sampler;
      uniform sampler2D trgls_sampler;
      in vec2 ftxt;
      out vec4 fColor;

      void main()
      {
        float alpha;
        fColor = texture(base_sampler, ftxt);

        vec4 uColor = texture(underlay_sampler, ftxt);
        alpha = uColor.a;
        fColor = (1.-alpha)*fColor + alpha*uColor;

        vec4 frColor = texture(trgls_sampler, ftxt);
        alpha = frColor.a;
        // alpha = 0.;
        fColor = (1.-alpha)*fColor + alpha*frColor;

        vec4 oColor = texture(overlay_sampler, ftxt);
        alpha = oColor.a;
        fColor = (1.-alpha)*fColor + alpha*oColor;
      }
    ''',
}

"""
data_code = {
    "name": "data",

    "vertex": '''
      #version 410 core

      uniform mat4 xform;
      layout(location=3) in vec3 xyz;
      layout(location=4) in vec2 stxy;
      out vec3 fxyz;
      void main() {
        gl_Position = xform*vec4(stxy, 0., 1.);
        fxyz = xyz;
      }
    ''',

    "geometry": '''
      #version 410 core
      
      layout(triangles) in;
      layout(triangle_strip, max_vertices=3) out;
      out vec2 bary2;

      void main() {
        for (int i=0; i<3; i++) {
          vec3 ob = vec3(0.);
          ob[i] = 1.;
          vec4 pos = gl_in[i].gl_Position;
          gl_Position = pos;
          bary2 = vec2(ob[0],ob[1]);
          EmitVertex();
        }
      }
    ''',

    "fragment": '''
      #version 410 core

      in vec3 fxyz;
      in vec2 bary2;
      uniform vec4 color;
      out vec4 fColor;

      void main() {
        vec3 bary = vec3(bary2, 1.-bary2[0]-bary2[1]);
        if (
          bary[0]<=0. || bary[0]>=1. ||
          bary[1]<=0. || bary[1]>=1. ||
          bary[2]<=0. || bary[2]>=1.) {
            discard;
        }
        fColor = vec4(bary, 1.);
      }
    ''',
}
"""

xyz_code = {
    "name": "xyz",

    "vertex": '''
      #version 410 core

      uniform mat4 xform;
      layout(location=3) in vec3 xyz;
      layout(location=4) in vec2 stxy;
      out vec3 fxyz;
      void main() {
        gl_Position = xform*vec4(stxy, 0., 1.);
        fxyz = xyz;
      }
    ''',

    "fragment": '''
      #version 410 core

      in vec3 fxyz;
      out vec4 fColor;

      void main() {
          fColor = vec4(fxyz/65535., 1.);
      }

    ''',
}

trgls_code = {
    "name": "trgls",

    "vertex": '''
      #version 410 core

      uniform mat4 xform;
      layout(location=3) in vec3 xyz;
      layout(location=4) in vec2 stxy;
      // out vec3 fxyz;
      void main() {
        gl_Position = xform*vec4(stxy, 0., 1.);
        // fxyz = xyz;
      }
    ''',

    "geometry_template": '''
      #version 410 core

      uniform float thickness;
      uniform vec2 window_size;

      layout(triangles) in;
      // 42 = 14*3
      layout(triangle_strip, max_vertices=42) out;

      %s

      void draw_line(vec4 pcs[2]);

      void main()
      {
        vec2 xys[3];
        bool xslo = true; // true if all xs are less than -limit
        bool xshi = true; // true if all xs are greater than limit
        bool yslo = true; // true if all ys are less than -limit
        bool yshi = true; // true if all ys are greater than limit
        float limit = 1.1;
        for (int i=0; i<3; i++) {
          vec2 xy = gl_in[i].gl_Position.xy;
          xys[i] = xy;
          if (xy.x > -limit) xslo = false;
          if (xy.x < limit) xshi = false;
          if (xy.y > -limit) yslo = false;
          if (xy.y < limit) yshi = false;
        }
        if (xslo || xshi || yslo || yshi) return;
        /*
        for (int i=0; i<4; i++) {
          int ii = i%%3;
          gl_Position = vec4(xys[ii], 0., 1.);
          EmitVertex();
          gl_Position = vec4(xys[ii], 0., 1.);
          EmitVertex();
        }
        */
        /*
        for (int i=0; i<3; i++) {
          gl_Position = vec4(xys[i], 0., 1.);
          EmitVertex();
        }
        */
        for (int i=0; i<3; i++) {
          int ip1 = (i+1)%%3;
          vec4 pcs[2];
          pcs[0] = vec4(xys[i], 0., 1.);
          pcs[1] = vec4(xys[ip1], 0., 1.);
          draw_line(pcs);
        }
      }

      void draw_line(vec4 pcs[2]) {
        int vcount = 4;
        if (thickness < 5) {
          vcount = 4;
        } else {
           vcount = 10;
        }

        vec2 tan = (pcs[1]-pcs[0]).xy;
        if (tan.x == 0 && tan.y == 0) {
          tan.x = 1.;
          tan.y = 0.;
        }
        tan = normalize(tan);
        vec2 norm = vec2(-tan.y, tan.x);
        vec2 factor = vec2(1./window_size.x, 1./window_size.y);
        vec4 offsets[9];
        for (int i=0; i<9; i++) {
          // trig contains cosine and sine of angle i*45 degrees
          vec2 trig = trig_table[i];
          vec2 raw_offset = -trig.x*tan + trig.y*norm;
          vec4 scaled_offset = vec4(factor*raw_offset, 0., 0.);
          offsets[i] = scaled_offset;
        }
        ivec2 vs[10];
        if (vcount == 10) {
          vs = v10;
        } else if (vcount == 4) {
          vs = v4;
        }

        for (int i=0; i<vcount; i++) {
          ivec2 iv = vs[i];
          gl_Position = pcs[iv.x] + thickness*offsets[iv.y];
          EmitVertex();
        }
        EndPrimitive();
      }

    ''',

    "fragment": '''
      #version 410 core

      // in vec3 fxyz;
      uniform vec4 frag_color;
      out vec4 fColor;

      void main() {
          // fColor = vec4(fxyz/65535., 1.);
          // fColor = vec4(.2,.8,.2,.8);
          fColor = frag_color;
      }

    ''',
}

trgl_pts_code = {
    "name": "trgl_pts",

    "vertex": '''
      #version 410 core

      uniform vec4 node_color;
      uniform vec4 highlight_node_color;
      uniform int nearby_node_id;
      out vec4 color;
      uniform mat4 xform;
      layout(location=4) in vec2 stxy;
      void main() {
        if (gl_VertexID == nearby_node_id) {
          color = highlight_node_color;
        } else {
          color = node_color;
        }
        gl_Position = xform*vec4(stxy, 0.0, 1.0);
      }

    ''',
    "fragment": '''
      #version 410 core

      in vec4 color;
      out vec4 fColor;

      void main()
      {
        fColor = color;
      }
    ''',
}
    
class GLSurfaceWindowChild(GLDataWindowChild):
    def __init__(self, gldw, parent=None):
        super(GLSurfaceWindowChild, self).__init__(gldw, parent)

    def localInit(self):
        # This corresponds to the line in the vertex shader(s):
        # layout(location=3) in vec3 xyx;
        self.xyz_location = 3
        # This corresponds to the line in the vertex shader(s):
        # layout(location=4) in vec3 stxy;
        self.stxy_location = 4
        self.message_prefix = "sw"
        # Cache these so we can recalculate the atlas 
        # whenever volume_view or volume_view.direction change
        self.volume_view =  None
        self.volume_view_direction = -1
        self.active_fragment = None
        self.atlas = None
        self.active_vao = None
        self.data_fbo = None
        self.xyz_fbo = None
        self.xyz_arr = None
        self.trgls_fbo = None
        # self.atlas_chunk_size = 254
        self.atlas_chunk_size = 126
        # self.atlas_chunk_size = 62

    def localInitializeGL(self):
        f = self.gl
        f.glClearColor(.6,.3,.3,1.)
        self.buildPrograms()
        self.buildSliceVao()
        self.printInfo()

    def setDefaultViewport(self):
        f = self.gl
        f.glViewport(0, 0, self.vp_width, self.vp_height)
    
    def resizeGL(self, width, height):
        f = self.gl

        # See https://doc.qt.io/qt-6/highdpi.html for why
        # this is needed when working with OpenGL.
        # I would prefer to set the size based on the size of
        # the default framebuffer (or viewport), but because of 
        # the PySide6 bug mentioned above, this does not seem
        # to be possible.
        ratio = self.screen().devicePixelRatio()
        width = int(ratio*width)
        height = int(ratio*height)
        
        self.vp_width = width
        self.vp_height = height
        vp_size = QSize(width, height)
        # print("resizeGL (surface)", width, height, vp_size)

        # fbo where xyz positions are drawn; this information is used
        # to determine which data chunks to load.
        # (at the moment) in the CPU rather than the GPU.
        # based on https://stackoverflow.com/questions/59338015/minimal-opengl-offscreen-rendering-using-qt
        vp_size = QSize(width, height)
        fbo_format = QOpenGLFramebufferObjectFormat()
        fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        # We would prefer to store the xyz information as floats.
        # However, in Qt5, QFrameworkBufferObject.toImage() creates
        # a uint8 QImage from a float32 fbo.  uint8 is too low
        # a resolution for our purposes!
        # The uint16 format can store xyz at a resolution of 1
        # pixel, which is good enough for our purposes.
        # fbo_format.setInternalTextureFormat(pygl.GL_RGB32F)
        fbo_format.setInternalTextureFormat(pygl.GL_RGBA16)
        self.xyz_fbo = QOpenGLFramebufferObject(vp_size, fbo_format)
        self.xyz_fbo.bind()
        draw_buffers = (pygl.GL_COLOR_ATTACHMENT0,)
        f.glDrawBuffers(len(draw_buffers), draw_buffers)

        # fbo where the data will be drawn
        fbo_format = QOpenGLFramebufferObjectFormat()
        fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        fbo_format.setInternalTextureFormat(pygl.GL_RGBA16)
        self.data_fbo = QOpenGLFramebufferObject(vp_size, fbo_format)
        self.data_fbo.bind()
        draw_buffers = (pygl.GL_COLOR_ATTACHMENT0,)
        f.glDrawBuffers(len(draw_buffers), draw_buffers)

        # fbo where vertices and wireframe triangles will be drawn 
        fbo_format = QOpenGLFramebufferObjectFormat()
        fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        fbo_format.setInternalTextureFormat(pygl.GL_RGBA16)
        self.trgls_fbo = QOpenGLFramebufferObject(vp_size, fbo_format)
        self.trgls_fbo.bind()
        draw_buffers = (pygl.GL_COLOR_ATTACHMENT0,)
        f.glDrawBuffers(len(draw_buffers), draw_buffers)

        QOpenGLFramebufferObject.bindDefault()

        self.setDefaultViewport()
        
    def paintGL(self):
        self.checkAtlas()
        if self.volume_view is None:
            return

        # print("paintGL (surface)")
        f = self.gl
        f.glClearColor(.6,.3,.6,1.)
        f.glClear(pygl.GL_COLOR_BUFFER_BIT)
        self.paintSlice()

    def buildPrograms(self):
        self.xyz_program = self.buildProgram(xyz_code)
        self.slice_program = self.buildProgram(slice_code)
        trgls_code["geometry"] = trgls_code["geometry_template"] % self.common_offset_code
        self.trgls_program = self.buildProgram(trgls_code)
        self.trgl_pts_program = self.buildProgram(trgl_pts_code)

    # Rebuild atlas if volume_view or volume_view.direction
    # changes
    def checkAtlas(self):
        dw = self.gldw
        if dw.volume_view is None:
            self.volume_view = None
            self.volume_view_direction = -1
            self.active_fragment = None
            self.atlas = None
            return
        pv = dw.window.project_view
        mfv = None
        if pv is not None:
            mfv = pv.mainActiveFragmentView(unaligned_ok=True)
        # if mfv is None:
        #     dw.volume_view.setStxyTf(None)
        if self.volume_view != dw.volume_view or self.volume_view_direction != self.volume_view.direction or self.active_fragment != mfv :
            self.volume_view = dw.volume_view
            self.volume_view_direction = self.volume_view.direction
            self.active_fragment = mfv
            if self.atlas is None:
                if self.atlas_chunk_size < 65:
                    self.atlas = Atlas(self.volume_view, self.gl, tex3dsz=(2048,2048,70), chunk_size=self.atlas_chunk_size)
                else:
                    self.atlas = Atlas(self.volume_view, self.gl, tex3dsz=(2048,2048,400), chunk_size=self.atlas_chunk_size)
                self.atlas.clearData()

    def paintSlice(self):
        timera = Utils.Timer()
        timera.active = False
        timerb = Utils.Timer()
        # timerb.active = False
        dw = self.gldw
        volume_view = self.volume_view
        f = self.gl

        # viewing window width
        ww = self.size().width()
        wh = self.size().height()
        # viewing window half width
        whw = ww//2
        whh = wh//2

        pv = dw.window.project_view
        # mfv = pv.mainActiveFragmentView(unaligned_ok=True)
        mfv = self.active_fragment
        # if mfv is None:
        #     # print("No currently active fragment")
        #     return

        if self.active_vao is None or self.active_vao.fragment_view != mfv:
            self.active_vao = FragmentMapVao(
                    mfv, self.xyz_location, self.stxy_location, self.gl)

        fvao = self.active_vao

        vao = fvao.getVao()

        # NOTE that drawTrgls, drawTrglXyzs, and drawData all
        # asssume that self.active_vao has been bound; they
        # don't bind it themselves.
        vao.bind()

        # timera.time("xyz")
        self.drawTrglXyzs(self.xyz_fbo, self.xyz_program)
        timera.time("xyz 2")

        ''''''
        xform = self.stxyXform()
        self.xyz_arr = None
        if xform is not None:
            # NOTE that getBlocks reads from xyz_fbo, which has
            # just been written to
            larr, self.xyz_arr = self.getBlocks(self.xyz_fbo)
            # if zoom_level >= 0 and self.atlas is not None:
            if len(larr) > 0 and self.atlas is not None:
                if len(larr) >= self.atlas.max_nchunks-1:
                    larr = larr[:self.atlas.max_nchunks-1]
                maxxed_out = self.atlas.addBlocks(larr)
                if maxxed_out:
                    dw.window.zarrSlot(None)
        ''''''

        self.drawTrgls(self.trgls_fbo, self.trgls_program)

        # NOTE that drawData uses the blocks added in addBlocks;
        # xyToTijk uses self.xyz_arr, which is created by getBlocks 
        self.drawData()
        timera.time("data")

        vao.release()

        self.slice_program.bind()
        base_tex = self.data_fbo.texture()
        bloc = self.slice_program.uniformLocation("base_sampler")
        if bloc < 0:
            print("couldn't get loc for base sampler")
            return
        bunit = 1
        f.glActiveTexture(pygl.GL_TEXTURE0+bunit)
        f.glBindTexture(pygl.GL_TEXTURE_2D, base_tex)
        self.slice_program.setUniformValue(bloc, bunit)

        underlay_data = np.zeros((wh,ww,4), dtype=np.uint16)
        self.drawUnderlays(underlay_data)
        underlay_tex = self.texFromData(underlay_data, QImage.Format_RGBA64)
        uloc = self.slice_program.uniformLocation("underlay_sampler")
        if uloc < 0:
            print("couldn't get loc for underlay sampler")
            return
        uunit = 2
        f.glActiveTexture(pygl.GL_TEXTURE0+uunit)
        underlay_tex.bind()
        self.slice_program.setUniformValue(uloc, uunit)

        overlay_data = np.zeros((wh,ww,4), dtype=np.uint16)
        self.drawOverlays(overlay_data)
        overlay_tex = self.texFromData(overlay_data, QImage.Format_RGBA64)
        oloc = self.slice_program.uniformLocation("overlay_sampler")
        if oloc < 0:
            print("couldn't get loc for overlay sampler")
            return
        ounit = 3
        f.glActiveTexture(pygl.GL_TEXTURE0+ounit)
        overlay_tex.bind()
        self.slice_program.setUniformValue(oloc, ounit)

        tloc = self.slice_program.uniformLocation("trgls_sampler")
        if tloc < 0:
            print("couldn't get loc for trgls sampler")
            return
        tunit = 4
        f.glActiveTexture(pygl.GL_TEXTURE0+tunit)
        tex_ids = self.trgls_fbo.textures()
        trgls_tex_id = tex_ids[0]
        f.glBindTexture(pygl.GL_TEXTURE_2D, trgls_tex_id)
        self.slice_program.setUniformValue(tloc, tunit)

        f.glActiveTexture(pygl.GL_TEXTURE0)
        self.slice_vao.bind()
        self.slice_program.bind()
        f.glDrawElements(pygl.GL_TRIANGLES, 
                         self.slice_indices.size, pygl.GL_UNSIGNED_INT, VoidPtr(0))
        self.slice_program.release()

        ''' # For testing:
        larr, self.xyz_arr = self.getBlocks(self.xyz_fbo)
        # if zoom_level >= 0 and self.atlas is not None:
        if len(larr) > 0 and self.atlas is not None:
            if len(larr) >= self.atlas.max_nchunks-1:
                larr = larr[:self.atlas.max_nchunks-1]
            maxxed_out = self.atlas.addBlocks(larr)
            if maxxed_out:
                dw.window.zarrSlot(None)
        '''

        self.slice_vao.release()
        timera.time("combine")

        timerb.time("done")

    def printBlocks(self, blocks):
        for block in blocks:
            print(block)

    def blocksToSet(self, blocks):
        bset = set()
        for block in blocks:
            bset.add(tuple(block))
        return bset
        
    def getBlocks(self, fbo):
        timera = Utils.Timer()
        timera.active = False
        dw = self.gldw
        f = self.gl

        im = fbo.toImage(True)
        timera.time("get image")
        # print("im format", im.format())
        farr = self.npArrayFromQImage(im)
        # print("farr", farr.shape, farr.dtype)
        # df is decimation factor
        df = 4
        arr = farr[::df,::df,:]
        # print(farr.shape, arr.shape)
        timera.time("array from image")
        # print("arr", arr.shape, arr.dtype)
        zoom = dw.getZoom()
        # fuzz = 1.0 for full resolution; smaller fuzz values
        # give less resolution
        vol = dw.volume_view.volume
        if vol.is_zarr:
            nlevels = len(vol.levels)
        else:
            nlevels = 1
        fuzz = .75
        iscale = 1
        for izoom in range(nlevels):
            lzoom = 1./iscale
            if lzoom < 2*zoom*fuzz or izoom == nlevels-1:
                break
            iscale *= 2

        # 1/zoom, scale (assuming fuzz = 1.0)
        # 0. - 2. 1
        # 2. - 4. 2
        # 4. - 8. 4
        # 8. - 16. 8
        # 16. - 32. 16
        # print("zoom", zoom, iscale)
        dv = self.atlas_chunk_size*iscale
        zoom_level = izoom
        # look for xyz values where alpha is not zero
        nzarr = arr[arr[:,:,3] > 0][:,:3] // dv
        # print("nzarr", nzarr.shape, nzarr.dtype)

        if len(nzarr) == 0:
            return [], farr

        nzmin = nzarr.min(axis=0)
        nzmax = nzarr.max(axis=0)
        nzsarr = nzarr-nzmin
        dvarr = np.zeros(nzmax-nzmin+1, dtype=np.uint32)[:,:,:,np.newaxis]
        indices = np.indices(nzmax-nzmin+1).transpose(1,2,3,0)
        dvarr = np.concatenate((dvarr, indices), axis=3)
        dvarr[nzsarr[:,0],nzsarr[:,1], nzsarr[:,2],0] = 1
        larr = dvarr[dvarr[:,:,:,0] == 1][:,1:]+nzmin
        larr = np.concatenate((larr, np.full((len(larr),1), izoom)), axis=1)
        # print("larr shape", larr.shape, larr.dtype)
        # larr = larr[:, :3]

        cur_larr = larr[:,:3].copy()
        for izoom in range(zoom_level+1, nlevels):
            nxyzs = cur_larr // 2
            cur_larr = np.unique(nxyzs, axis=0)
            # print("cur_larr shape", cur_larr.shape, cur_larr.dtype)
            clarr = np.concatenate((cur_larr, np.full((len(cur_larr),1), izoom)), axis=1)
            # larr = np.concatenate((larr, np.concatenate((cur_larr, np.full((len(cur_larr),1), izoom)), axis=1)), axis=0)
            # larr = np.concatenate((larr, clarr), axis=0)

            larr = np.concatenate((clarr, larr), axis=0)
            # print("new larr shape", izoom, larr.shape, larr.dtype)

        timera.time("process image")

        return larr, farr

    def stxyXform(self):
        dw = self.gldw

        ww = dw.size().width()
        wh = dw.size().height()
        volume_view = self.volume_view

        zoom = dw.getZoom()
        cij = volume_view.stxytf
        if cij is None:
            return None
        # print("cij", cij)
        mat = np.zeros((4,4), dtype=np.float32)
        wf = zoom/(.5*ww)
        hf = zoom/(.5*wh)
        mat[0][0] = wf
        mat[0][3] = -wf*cij[0]
        mat[1][1] = -hf
        mat[1][3] = hf*cij[1]
        mat[3][3] = 1.
        xform = QMatrix4x4(mat.flatten().tolist())
        return xform

    '''
    def drawDataOrig(self):
        f = self.gl
        dw = self.gldw

        self.data_fbo.bind()

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        f.glClearColor(0.,0.,0.,0.)
        f.glClear(pygl.GL_COLOR_BUFFER_BIT)

        pv = dw.window.project_view
        mfv = pv.mainActiveFragmentView(unaligned_ok=True)
        if mfv is None:
            # print("No currently active fragment")
            return

        if self.active_vao is None or self.active_vao.fragment_view != mfv:
            self.active_vao = FragmentMapVao(
                    mfv, self.xyz_location, self.stxy_location, self.gl)

        fvao = self.active_vao

        vao = fvao.getVao()
        vao.bind()

        f.glDrawElements(pygl.GL_TRIANGLES, fvao.trgl_index_size,
                       pygl.GL_UNSIGNED_INT, None)
        vao.release()
        self.trgl_program.release()

        QOpenGLFramebufferObject.bindDefault()
    '''

    def drawData(self):
        if self.atlas is None:
            return
        stxy_xform = self.stxyXform()
        # if stxy_xform is None:
        #     return
        self.atlas.displayBlocks(self.data_fbo, self.active_vao, stxy_xform)

    # pts are in form stxy.x, stxy.y, index
    def getPointsInStxyWindow(self, fv, xywindow):
        pts = fv.stpoints
        matches = ((pts > xywindow[0]) & (pts < xywindow[1])).all(axis=1).nonzero()[0]
        mpts = pts[matches]
        # print("m", xywindow, len(pts), matches.shape, mpts.shape)
        # print("m", len(pts), matches.shape, mpts.shape)
        opts = np.concatenate((mpts, matches[:,np.newaxis]), axis=1)
        return opts


    # TODO: should this be in parent widget?
    def stxysToWindowXys(self, ijs):
        dw = self.gldw
        zoom = dw.getZoom()
        cij = self.volume_view.stxytf
        ci = cij[0]
        cj = cij[1]
        ww, wh = self.width(), self.height()
        wcx, wcy = ww//2, wh//2
        cij = np.array(cij)
        wc = np.array((wcx,wcy))
        xys = np.rint(zoom*(ijs-cij)+wc).astype(np.int32)
        return xys

    def drawTrgls(self, fbo, trgls_program):
        # bind program, bind fbo, assume vao is already bound
        f = self.gl
        dw = self.gldw
        fvao = self.active_vao

        fbo.bind()

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        f.glClearColor(0.,0.,0.,0.)
        f.glClear(pygl.GL_COLOR_BUFFER_BIT)
        xform = self.stxyXform()
        if xform is None:
            QOpenGLFramebufferObject.bindDefault()
            return

        f.glViewport(0, 0, fbo.width(), fbo.height())

        opacity = dw.getDrawOpacity("overlay")
        apply_line_opacity = dw.getDrawApplyOpacity("mesh")
        line_alpha = 1.
        if apply_line_opacity:
            line_alpha = opacity
        line_thickness = dw.getDrawWidth("mesh")
        line_thickness = (3*line_thickness)//2
        fv = fvao.fragment_view
        pv = dw.window.project_view

        if fv.visible and line_thickness != 0 and line_alpha != 0:
            trgls_program.bind()
            trgls_program.setUniformValue("xform", xform)

            wsize = QVector2D(fbo.width(), fbo.height())
            trgls_program.setUniformValue("window_size", wsize)

            tloc = self.trgls_program.uniformLocation("thickness")
            f.glUniform1f(tloc, 1.*line_thickness)

            qcolor = fv.fragment.color
            rgba = list(qcolor.getRgbF())
            rgba[3] = line_alpha
            self.trgls_program.setUniformValue("frag_color", *rgba)

            f.glDrawElements(pygl.GL_TRIANGLES, fvao.trgl_index_size,
                       pygl.GL_UNSIGNED_INT, VoidPtr(0))

            trgls_program.release()

        apply_node_opacity = dw.getDrawApplyOpacity("node")
        node_alpha = 1.
        if apply_node_opacity:
            node_alpha = opacity
        default_node_thickness = dw.getDrawWidth("node")
        free_node_thickness = dw.getDrawWidth("free_node")
        node_thickness = default_node_thickness
        if not fv.mesh_visible:
            node_thickness = free_node_thickness
        node_thickness *= 2
        
        dw.cur_frag_pts_xyijk = None
        dw.cur_frag_pts_fv = []
        xyptslist = []
        dw.nearbyNode = -1

        if fv.visible and node_thickness != 0 and node_alpha != 0:
            self.trgl_pts_program.bind()
            self.trgl_pts_program.setUniformValue("xform", xform)
            highlight_node_color = [c/65535 for c in dw.highlightNodeColor]
            highlight_node_color[3] = node_alpha
            self.trgl_pts_program.setUniformValue("highlight_node_color", *highlight_node_color)
            color = dw.nodeColor
            if not fv.active:
                color = dw.inactiveNodeColor
            if not fv.mesh_visible:
                color = fv.fragment.cvcolor
            rgba = [c/65535 for c in color]
            rgba[3] = node_alpha
            self.trgl_pts_program.setUniformValue("node_color", *rgba)

            nearby_node_id = 2**30
            xywindow = dw.stxyWindowBounds()
            # pts are in form stxy.x, stxy.y, index
            pts = self.getPointsInStxyWindow(fv, xywindow)
            xys = self.stxysToWindowXys(pts[:,:2])
            xyzs = fv.vpoints[np.int32(pts[:,2])]
            xypts = np.concatenate((xys, xyzs), axis=1)
            if len(xypts) > 0:
                dw.cur_frag_pts_xyijk = xypts
                dw.cur_frag_pts_stxy = pts
            else:
                dw.cur_frag_pts_xyijk = np.zeros((0,5), dtype=np.float32)
                dw.cur_frag_pts_stxy = np.zeros((0,3), dtype=np.float32)
            dw.cur_frag_pts_fv = [fv]*len(xypts)

            if fv == pv.nearby_node_fv:
                ind = pv.nearby_node_index
                nz = np.nonzero(pts[:,2] == ind)[0]
                if len(nz) > 0:
                    ind = nz[0]
                    self.nearbyNode = ind
                    nearby_node_id = int(pts[ind,2])

            # figure out highlighted node and set nearby_node_id
            nniloc = self.trgl_pts_program.uniformLocation("nearby_node_id")
            self.trgl_pts_program.setUniformValue(nniloc, int(nearby_node_id))
                
            f.glPointSize(node_thickness)
            f.glDrawArrays(pygl.GL_POINTS, 0, fvao.stxys_size)
            self.trgl_pts_program.release()

        QOpenGLFramebufferObject.bindDefault()

    def drawTrglXyzs(self, fbo, program):
        f = self.gl
        dw = self.gldw
        fvao = self.active_vao


        fbo.bind()

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        f.glClearColor(0.,0.,0.,0.)
        f.glClear(pygl.GL_COLOR_BUFFER_BIT)
        xform = self.stxyXform()
        if xform is None:
            QOpenGLFramebufferObject.bindDefault()
            return

        f.glViewport(0, 0, fbo.width(), fbo.height())

        program.bind()

        program.setUniformValue("xform", xform)

        f.glDrawElements(pygl.GL_TRIANGLES, fvao.trgl_index_size,
                       pygl.GL_UNSIGNED_INT, VoidPtr(0))
        program.release()

        QOpenGLFramebufferObject.bindDefault()
        self.setDefaultViewport()

    '''
    def drawXyz(self, fbo):
        f = self.gl
        dw = self.gldw
        fvao = self.active_vao
        xform = self.stxyXform()
        if xform is None:
            return

        fbo.bind()

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        f.glClearColor(0.,0.,0.,0.)
        f.glClear(pygl.GL_COLOR_BUFFER_BIT)
        f.glViewport(0, 0, fbo.width(), fbo.height())

        self.xyz_program.bind()

        self.xyz_program.setUniformValue("xform", xform)

        f.glDrawElements(pygl.GL_TRIANGLES, fvao.trgl_index_size,
                       pygl.GL_UNSIGNED_INT, None)
        self.xyz_program.release()

        QOpenGLFramebufferObject.bindDefault()
        self.setDefaultViewport()
    '''


# two attribute buffers: xyz, and stxy (st = scaled texture)
class FragmentMapVao:
    def __init__(self, fragment_view, xyz_loc, stxy_loc, gl):
        self.fragment_view = fragment_view
        self.gl = gl
        self.vao = None
        self.vao_modified = ""
        self.is_line = False
        self.xyz_loc = xyz_loc
        self.stxy_loc = stxy_loc
        self.getVao()

    def getVao(self):
        fv = self.fragment_view
        if fv is not None and self.vao_modified > fv.modified and self.vao_modified > fv.fragment.modified and self.vao_modified > fv.local_points_modified:
            # print("returning existing vao")
            return self.vao

        self.vao_modified = Utils.timestamp()

        if self.vao is None:
            self.vao = QOpenGLVertexArrayObject()
            self.vao.create()
            # print("creating new vao")

        if fv is None:
            return self.vao

        # print("updating vao")
        self.vao.bind()

        f = self.gl

        self.xyz_vbo = QOpenGLBuffer()
        self.xyz_vbo.create()
        self.xyz_vbo.bind()

        xyzs = np.ascontiguousarray(fv.vpoints[:,:3], dtype=np.float32)
        self.xyzs_size = xyzs.size

        nbytes = xyzs.size*xyzs.itemsize
        self.xyz_vbo.allocate(xyzs, nbytes)

        f.glVertexAttribPointer(
                self.xyz_loc,
                xyzs.shape[1], int(pygl.GL_FLOAT), int(pygl.GL_FALSE), 
                0, VoidPtr(0))
        self.xyz_vbo.release()
        # This needs to be called while the current VAO is bound
        f.glEnableVertexAttribArray(self.xyz_loc)

        self.stxy_vbo = QOpenGLBuffer()
        self.stxy_vbo.create()
        self.stxy_vbo.bind()

        stxys = np.ascontiguousarray(fv.stpoints, dtype=np.float32)
        self.stxys_size = stxys.size

        nbytes = stxys.size*stxys.itemsize
        self.stxy_vbo.allocate(stxys, nbytes)
        f.glVertexAttribPointer(
                self.stxy_loc,
                stxys.shape[1], int(pygl.GL_FLOAT), int(pygl.GL_FALSE), 
                0, VoidPtr(0))
        self.stxy_vbo.release()
        # This needs to be called while the current VAO is bound
        f.glEnableVertexAttribArray(self.stxy_loc)

        self.ibo = QOpenGLBuffer(QOpenGLBuffer.IndexBuffer)
        self.ibo.create()
        self.ibo.bind()

        # We may have a line, not a triangulated surface.
        # Notice that indices must be uint8, uint16, or uint32
        fv_trgls = fv.trgls()
        self.is_line = False
        if fv_trgls is None:
            fv_line = fv.line
            if fv_line is not None:
                self.is_line = True
                # Despite the name "fv_trgls",
                # this contains a line strip if self.is_line is True.
                fv_trgls = fv.line[:,2]
            else:
                fv_trgls = np.zeros((0,3), dtype=np.uint32)
        
        trgls = np.ascontiguousarray(fv_trgls, dtype=np.uint32)

        self.trgl_index_size = trgls.size

        nbytes = trgls.size*trgls.itemsize
        self.ibo.allocate(trgls, nbytes)

        # print("nodes, trgls", pts3d.shape, trgls.shape)

        self.vao.release()
        
        # do not release ibo before vao is released!
        self.ibo.release()

        return self.vao



        self.makeCurrent()
        self.logger.stopLogging()
        print("stopped logging")
        # e.accept()

# gl is the OpenGL function holder
# arr is the numpy array
# uniform_index is the location of the uniform block in the shader
# binding_point is the binding point
# To use: modify values in the data member, then call setBuffer().
class UniBuf:
    def __init__(self, gl, arr, binding_point):
        gl = pygl
        self.gl = gl
        self.binding_point = binding_point
        self.data = arr
        self.buffer_id = gl.glGenBuffers(1)
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, self.binding_point, self.buffer_id)
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, 0)
        self.setBuffer()

    def bindToShader(self, shader_id, uniform_index):
        gl = self.gl
        gl.glUniformBlockBinding(shader_id, uniform_index, self.binding_point)

    def setBuffer(self):
        gl = self.gl
        byte_size = self.data.size * self.data.itemsize
        # print("about to bind buffer", self.buffer_id)
        gl.glBindBuffer(pygl.GL_UNIFORM_BUFFER, self.buffer_id)
        # pygl.glBufferData(pygl.GL_UNIFORM_BUFFER, byte_size, self.data.tobytes(), pygl.GL_STATIC_DRAW)
        # print("about to set buffer", self.data.shape, self.data.dtype)
        gl.glBufferData(gl.GL_UNIFORM_BUFFER, byte_size, self.data, gl.GL_STATIC_DRAW)
        # print("buffer has been set")
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, 0)


# The Chunk class is used by the Atlas class
# see below) to keep track of data stored in
# the 3D texture atlas.
# Variable naming conventions:
# d: data, a: atlas, c: chunk, pc: padded chunk
# _: corner, k: key, l: level
# _: coords, sz: size, e: single coord, r: rect
#
# coordinates are (x, y, z);
# the data value at (x, y, z) is accessed by data[z][y][x]

class Chunk:
    def __init__(self, atlas, ak, dk, dl):
        # atlas, ak, dk, dl
        # Given atlas, atlas key, data key, data level
        # copy chunk from data to atlas_data
        # compute xform

        # Atlas
        self.atlas = atlas
        # Chunk key (position) in atlas (3 coords)
        self.ak = ak
        # Chunk key (position) in input data (3 coords: x, y, z)

        # atlas chunk size (3 coords, usually 128,128,128)
        acsz = atlas.acsz
        # atlas rectangle
        ar = self.k2r(ak, acsz)
        self.ar = ar
        # atlas corner
        a = ar[0]

        # padding (scalar, usually 1)
        self.pad = atlas.pad

        # size of the atlas (3 coords: nx, ny, nz)
        asz = atlas.asz
        # rectangle of the entire data set

        self.setData(dk, dl)
        self.in_use = False
        self.misses = -1


    def setData(self, dk, dl):
        # print("set data", self.ak, dk, dl)
        self.dk = dk
        self.dl = dl
        if dl < 0:
            return False

        # data chunk size (3 coords, usually 128,128,128)
        dcsz = self.atlas.dcsz 
        # data rectangle
        dr = self.k2r(dk, dcsz)
        # data corner
        d = dr[0]

        # padded data rectangle
        pdr = self.padRect(dr, self.pad)
        # size of the data on the data's level (3 coords: nx, ny, nz)
        dsz = self.atlas.dsz[dl]
        all_dr = ((0, 0, 0), (dsz[0], dsz[1], dsz[2]))
        # intersection of the padded data rectangle with the data
        int_dr = self.rectIntersection(pdr, all_dr)
        if int_dr is None:
            return False
        # print(pdr, all_dr, int_dr)

        # Compute change in pdr (padded data-chunk rectangle) 
        # due to intersection with edges of data array:
        # Difference in min corner:
        skip0 = tuple(int_dr[0][i]-pdr[0][i] for i in range(len(int_dr[0])))
        # Difference in max corner:
        skip1 = tuple(pdr[1][i]-int_dr[1][i] for i in range(len(pdr[1])))

        # print(pdr, skip0)
        # print(ar, int_dr, skip0, skip1)
        # print(skip0, skip1)
        # print(dr, int_dr)
        acsz = self.atlas.acsz
        buf = np.zeros((acsz[2], acsz[1], acsz[0]), np.uint16)
        c0 = skip0
        c1 = tuple(acsz[i]-skip1[i] for i in range(len(acsz)))
        data = self.atlas.datas[dl]

        timera = Utils.Timer()
        timera.active = False
        # TODO: eliminate need for is_zarr test by adding
        # getDataAndMisses to VolumeView.trdata (need to make
        # trdata into a class)
        if self.atlas.volume_view.volume.is_zarr:
            buf[c0[2]:c1[2], c0[1]:c1[1], c0[0]:c1[0]], misses = data.getDataAndMisses(slice(int_dr[0][2],int_dr[1][2]), slice(int_dr[0][1],int_dr[1][1]), slice(int_dr[0][0],int_dr[1][0]), False)
            # print(self.ak, misses)
            print(self.dk, self.dl, misses)
        else:
            self.atlas.volume_view.volume.setImmediateDataMode(True)
            buf[c0[2]:c1[2], c0[1]:c1[1], c0[0]:c1[0]] = data[int_dr[0][2]:int_dr[1][2], int_dr[0][1]:int_dr[1][1], int_dr[0][0]:int_dr[1][0]]
            self.atlas.volume_view.volume.setImmediateDataMode(False)
            misses = 0

        self.misses = misses
        timera.time("get data")

        texture_set = False
        # print("buf", buf.min(), buf.max())
        a = self.ar[0]
        # print(a, acsz)
        if self.misses == 0:
            self.atlas.tex3d.setData(a[0], a[1], a[2], acsz[0], acsz[1], acsz[2], QOpenGLTexture.Red, QOpenGLTexture.UInt16, buf.tobytes())
            texture_set = True
            self.tmin = tuple((dr[0][i])/dsz[i] for i in range(len(dsz)))
            self.tmax = tuple((dr[1][i])/dsz[i] for i in range(len(dsz)))
            timera.time("set texture")
        else:
            self.tmin = (0., 0., 0.)
            self.tmax = (-1., -1., -1.)
            timera.time("didn't set texture")

        asz = self.atlas.asz

        xform = QMatrix4x4()
        xform.scale(*(1./asz[i] for i in range(len(asz))))
        xform.translate(*(self.ar[0][i]+self.pad-dr[0][i] for i in range(len(self.ar[0]))))
        xform.scale(*(dsz[i] for i in range(len(dsz))))
        self.xform = xform

        self.atlas.program.bind()
        ind = self.atlas.index(self.ak)

        self.atlas.tmax_ubo.data[ind, :3] = self.tmax
        self.atlas.tmin_ubo.data[ind, :3] = self.tmin

        xformarr = np.array(xform.transposed().copyDataTo(), dtype=np.float32).reshape(4,4)
        self.atlas.xform_ubo.data[ind, :, :] = xformarr

        # Now consolidated in addBlocks
        # self.atlas.tmin_ubo.setBuffer()
        # self.atlas.tmax_ubo.setBuffer()
        # self.atlas.xform_ubo.setBuffer()

        timera.time("set buffers")

        self.in_use = True
        return texture_set

    @staticmethod
    def k2r(k, csz):
        c = tuple(k[i]*csz[i] for i in range(len(k)))
        r = (c, tuple(c[i]+csz[i] for i in range(len(c))))
        return r

    # padded rectangle
    @staticmethod
    def padRect(rect, pad):
        r = (tuple(rect[0][i]-pad for i in range(len(rect[0]))),
             tuple(rect[1][i]+pad for i in range(len(rect[1]))))
        return r

    # adapted from https://stackoverflow.com/questions/25068538/intersection-and-difference-of-two-rectangles/25068722#25068722
    @staticmethod
    def rectIntersection(ra, rb):
        (ax1, ay1, az1), (ax2, ay2, az2) = ra
        (bx1, by1, bz1), (bx2, by2, bz2) = rb
        # print(ra, rb)
        x1 = max(min(ax1, ax2), min(bx1, bx2))
        y1 = max(min(ay1, ay2), min(by1, by2))
        z1 = max(min(az1, az2), min(bz1, bz2))
        x2 = min(max(ax1, ax2), max(bx1, bx2))
        y2 = min(max(ay1, ay2), max(by1, by2))
        z2 = min(max(az1, az2), max(bz1, bz2))
        if (x1<x2) and (y1<y2) and (z1<z2):
            r = ((x1, y1, z1), (x2, y2, z2))
            # print(r)
            return r

atlas_data_code = {
    "name": "atlas_data",

    "vertex": '''
      #version 410 core

      uniform mat4 stxy_xform;
      uniform mat4 xyz_xform;
      layout(location=3) in vec3 xyz;
      layout(location=4) in vec2 stxy;
      out vec4 fxyz;
      void main() {
        gl_Position = stxy_xform*vec4(stxy, 0., 1.);
        fxyz = xyz_xform*vec4(xyz, 1.);
      }
    ''',

    "fragment_template": '''
      #version 410 core

      const int max_nchunks = {max_nchunks};
      // NOTE: On an XPS 9320 running PyQt5 and OpenGL 4.1,
      // the uniform buffers below MUST be in alphabetical
      // order!!
      layout (std140) uniform TMaxs {{
        vec3 tmaxs[max_nchunks];
      }};
      layout (std140) uniform TMins {{
        vec3 tmins[max_nchunks];
      }};
      layout (std140) uniform XForms {{
        mat4 xforms[max_nchunks];
      }};
      layout (std140) uniform ChartIds {{
        int chart_ids[max_nchunks];
      }};
      uniform sampler3D atlas;
      uniform int ncharts;

      in vec4 fxyz;
      out vec4 fColor;

      void main() {{
        fColor = vec4(.5,.5,.5,1.);
        for (int i=0; i<ncharts; i++) {{
        // for (int i=ncharts-1; i>=0; i--) {{
            int id = chart_ids[i];
            vec3 tmin = tmins[id];
            vec3 tmax = tmaxs[id];
            if (tmin.z != 0. && fxyz.x >= tmin.x && fxyz.x <= tmax.x &&
             fxyz.y >= tmin.y && fxyz.y <= tmax.y &&
             fxyz.z >= tmin.z && fxyz.z <= tmax.z) {{
              mat4 xform = xforms[id];
              vec3 txyz = (xform*fxyz).xyz;
              fColor = texture(atlas, txyz);
              fColor.g = fColor.r;
              fColor.b = fColor.r;
              fColor.a = 1.;
            }}
        }}

      }}
    ''',
}

# Atlas implements a 3D texture atlas.  The 3D OpenGL texture
# (the atlas) is subdivided into chunks; each atlas chunk stores
# a scroll data chunk (conventionally 128^3 in size).  
# NOTE that the data chunk size used in Atlas is NOT related
# to the zarr chunk size, if any, that is used to store
# the scroll data on disk.
# Each atlas chunk # is padded (to prevent texture bleeding) so 
# by default each atlas chunk is 130^ in size.
# The Atlas class keeps track of which data chunk is stored in
# whice atlas chunk.  As new data chunks are added, old data
# chunks are removed as needed.
# The chunks (with scroll data location and texture location)
# are stored in an OrderedDict.  In-use chunks are kept at the
# end of this dict.

class Atlas:
    # def __init__(self, volume_view, gl, tex3dsz=(2048,1500,150), dcsz=(128,128,128)):
    # def __init__(self, volume_view, gl, tex3dsz=(2048,2048,600), dcsz=(256,256,256)):
    def __init__(self, volume_view, gl, tex3dsz=(2048,2048,300), chunk_size=126):
        dcsz = (chunk_size, chunk_size, chunk_size)
        self.gl = gl
        pad = 1
        self.pad = pad
        self.volume_view = volume_view
        self.dcsz = dcsz
        acsz = tuple(dcsz[i]+2*pad for i in range(len(dcsz)))
        self.acsz = acsz
        vol = volume_view.volume
        vdir = volume_view.direction
        is_zarr = vol.is_zarr
        if chunk_size < 65:
            self.max_textures_set = 10
        else:
            self.max_textures_set = 3

        datas = []
        if not is_zarr:
            data = vol.trdatas[vdir]
            datas.append(data)
        else:
            for level in vol.levels:
                data = level.trdatas[vdir]
                datas.append(data)
        dsz = []
        for data in datas:
            shape = data.shape
            dsz.append(tuple(shape[::-1]))
        self.datas = datas
        self.dsz = dsz
        # number of data chunks in each direction
        ksz = []
        for l in range(len(dsz)):
            lksz = tuple(self.ke(dsz[l][i],dcsz[i]) for i in range(len(dcsz)))
            ksz.append(lksz)
        self.ksz = ksz
        # number of atlas chunks in each direction
        aksz = tuple(tex3dsz[i]//acsz[i] for i in range(len(acsz)))
        # size of atlas in each direction
        self.asz = tuple(aksz[i]*acsz[i] for i in range(len(acsz)))
        self.aksz = aksz

        self.chunks = OrderedDict()

        for k in range(aksz[2]):
            for j in range(aksz[1]):
                for i in range(aksz[0]):
                    ak = (i,j,k)
                    dk = (i,j,k)
                    dl = -1
                    chunk = Chunk(self, ak, dk, dl)
                    key = self.key(dk, dl)
                    self.chunks[key] = chunk

        max_nchunks = aksz[0]*aksz[1]*aksz[2]
        print("max_nchunks", max_nchunks)
        self.max_nchunks = max_nchunks
        atlas_data_code["fragment"] = atlas_data_code["fragment_template"].format(max_nchunks = max_nchunks)
        self.program = GLDataWindowChild.buildProgram(atlas_data_code)
        self.program.bind()
        xyz_xform = self.xyzXform(dsz[0])
        self.program.setUniformValue("xyz_xform", xyz_xform)
        # for var in ["atlas", "xyz_xform", "tmins", "tmaxs", "TMins", "TMaxs", "XForms", "ZChartIds", "chart_ids", "ncharts"]:
        #     print(var, self.program.uniformLocation(var))
        pid = self.program.programId()
        print("program id", pid)

        # the 0 is the binding point, which should be unique for
        # each UniBuf.
        # should use glGetUniformBlockIndex, to get ubo_index instead
        # of hardwiring 0, but that function is missing from PyQt5
        # for var in ["TMaxs", "TMins", "XForms", "ZChartIds"]:
        #    print(var, gl.glGetUniformBlockIndex(pid, var))
        self.tmax_ubo = UniBuf(gl, np.zeros((max_nchunks, 4), dtype=np.float32), 0)
        loc = gl.glGetUniformBlockIndex(pid, "TMaxs")
        self.tmax_ubo.bindToShader(pid, loc)

        self.tmin_ubo = UniBuf(gl, np.zeros((max_nchunks, 4), dtype=np.float32), 1)
        loc = gl.glGetUniformBlockIndex(pid, "TMins")
        self.tmin_ubo.bindToShader(pid, loc)

        self.xform_ubo = UniBuf(gl, np.zeros((max_nchunks, 4, 4), dtype=np.float32), 2)
        loc = gl.glGetUniformBlockIndex(pid, "XForms")
        self.xform_ubo.bindToShader(pid, loc)

        # even though data in this case could be listed as a 1D
        # array of ints, UBO layout rules require that the ints
        # be aligned every 16 bytes.
        self.chart_id_ubo = UniBuf(gl, np.zeros((max_nchunks, 4), dtype=np.int32), 3)
        loc = gl.glGetUniformBlockIndex(pid, "ChartIds")
        self.chart_id_ubo.bindToShader(pid, loc)

        # allocate 3D texture 
        tex3d = QOpenGLTexture(QOpenGLTexture.Target3D)
        tex3d.setWrapMode(QOpenGLTexture.ClampToBorder)
        tex3d.setAutoMipMapGenerationEnabled(False)
        tex3d.setMagnificationFilter(QOpenGLTexture.Linear)
        # tex3d.setMagnificationFilter(QOpenGLTexture.Nearest)
        tex3d.setMinificationFilter(QOpenGLTexture.Linear)
        # width, height, depth
        tex3d.setSize(*self.asz)
        # see https://stackoverflow.com/questions/23533749/difference-between-gl-r16-and-gl-r16ui
        tex3d.setFormat(QOpenGLTexture.R16_UNorm)
        tex3d.allocateStorage()
        self.tex3d = tex3d
        aunit = 4
        gl.glActiveTexture(pygl.GL_TEXTURE0+aunit)
        tex3d.bind()
        # self.program.setUniformValue("atlas", aunit)
        aloc = self.program.uniformLocation("atlas")
        self.program.setUniformValue(aloc, aunit)
        gl.glActiveTexture(pygl.GL_TEXTURE0)
        tex3d.release()

    def clearData(self):
        aksz = self.aksz
        self.chunks.clear()
        for k in range(aksz[2]):
            for j in range(aksz[1]):
                for i in range(aksz[0]):
                    ak = (i,j,k)
                    dk = (i,j,k)
                    dl = -1
                    chunk = Chunk(self, ak, dk, dl)
                    key = self.key(dk, dl)
                    self.chunks[key] = chunk

    def xyzXform(self, data_size):
        mat = np.zeros((4,4), dtype=np.float32)
        mat[0][0] = 1./data_size[0]
        mat[1][1] = 1./data_size[1]
        mat[2][2] = 1./data_size[2]
        mat[3][3] = 1.
        xform = QMatrix4x4(mat.flatten().tolist())
        return xform

    def key(self, dk, dl):
        return (dl, dk[2], dk[1], dk[0])

    # given an atlas chunk location, return a key
    def index(self, ak):
        aksz = self.aksz
        return (ak[2]*aksz[1] + ak[1])*aksz[0] + ak[0]

    # Number of chunks (in 1D) given data size, chunk size.
    # This gives the number of chunks needed to cover the
    # entire data set; the last chunk may stretch beyond
    # the end of the data.
    def ke(self, e, ce):
        ke = 1 + (e-1)//ce
        return ke

    # Given a list of blocks, add the blocks that are
    # not already in the atlas. 
    def addBlocks(self, zblocks):
        for chunk in reversed(self.chunks.values()):
            if chunk.in_use == False:
                break
            chunk.in_use = False
        textures_set = 0
        for zblock in zblocks:
            # if textures_set >= self.max_textures_set:
            #     continue
            block = zblock[:3]
            zoom_level = zblock[3]
            key = self.key(block, zoom_level)
            chunk = self.chunks.get(key, None)
            # If the data chunk is not currently stored in the atlas:
            if chunk is None:
                if textures_set >= self.max_textures_set:
                    continue
                # Get the first Chunk in the OrderedDict: 
                _, chunk = self.chunks.popitem(last=False)
                # print("popped", chunk.dk, chunk.dl)
                texture_set = chunk.setData(block, zoom_level)
                # print("set data", chunk.dk, chunk.dl)
                if texture_set:
                    textures_set += 1
                self.chunks[key] = chunk
            else: # If the data is already in the Atlas
                # move the chunk to the end of the OrderedDict
                # if chunk.misses > 0:
                if chunk.misses > 0 and textures_set < self.max_textures_set:
                    texture_set = chunk.setData(block, zoom_level)
                    if texture_set:
                        textures_set += 1
                self.chunks.move_to_end(key)
            chunk.in_use = True

        # TODO: At img 12310 x 3348 y 4539 there is a little missing piece 

        if textures_set > 0:
            self.tmin_ubo.setBuffer()
            self.tmax_ubo.setBuffer()
            self.xform_ubo.setBuffer()
        cnt = 0
        # To get all the active chunks, search backwards from
        # the end
        for key,chunk in reversed(self.chunks.items()):
            if not chunk.in_use:
                break
            # print(chunk.dl, chunk.dk)
            cnt += 1
        # print(zoom_level, cnt, len(blocks))
        return textures_set >= self.max_textures_set
            
    # displayBlocks is in a separate operation
    # than addBlocks, because addBlocks may need to be called later
    # than displayBlocks, to prevent GPU round trips
    def displayBlocks(self, data_fbo, fvao, stxy_xform):
        gl = self.gl

        data_fbo.bind()

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        gl.glClearColor(0.,0.,0.,0.)
        gl.glClear(pygl.GL_COLOR_BUFFER_BIT)

        if stxy_xform is None:
            QOpenGLFramebufferObject.bindDefault()
            return

        self.program.bind()

        self.program.setUniformValue("stxy_xform", stxy_xform)

        '''
        nchunks = 0
        for key,chunk in reversed(self.chunks.items()):
            if not chunk.in_use:
                break
            ak = chunk.ak
            ind = self.index(ak)
            # self.program.setUniformValue("chart_ids[%d]"%nchunks, ind)
            self.chart_id_ubo.data[nchunks,0] = ind
            # print(nchunks, ind)
            nchunks += 1
        '''
        uchunks = []
        for key,chunk in reversed(self.chunks.items()):
            if not chunk.in_use:
                break
            uchunks.append(chunk)
        uchunks.sort(reverse=True, key=lambda chunk: chunk.dl)
        nchunks = 0
        for chunk in uchunks:
            ak = chunk.ak
            ind = self.index(ak)
            # self.program.setUniformValue("chart_ids[%d]"%nchunks, ind)
            self.chart_id_ubo.data[nchunks,0] = ind
            nchunks += 1

        # BUG in PySide6
        # Calls Uniform4fv
        # self.program.setUniformValue("ncharts", nchunks)
        nloc = self.program.uniformLocation("ncharts")
        # print("nloc, nchunks", nloc, nchunks)
        print("nchunks", nchunks)
        gl.glUniform1i(nloc, nchunks)

        self.chart_id_ubo.setBuffer()

        # print("db de")
        gl.glDrawElements(pygl.GL_TRIANGLES, fvao.trgl_index_size,
                       pygl.GL_UNSIGNED_INT, VoidPtr(0))
        # print("db de finished")
        self.program.release()

        QOpenGLFramebufferObject.bindDefault()
