from PyQt5.QtGui import (
        QImage,
        QMatrix4x4,
        QOffscreenSurface,
        QOpenGLVertexArrayObject,
        QOpenGLBuffer,
        QOpenGLContext,
        QOpenGLDebugLogger,
        QOpenGLDebugMessage,
        QOpenGLFramebufferObject,
        QOpenGLFramebufferObjectFormat,
        QOpenGLShader,
        QOpenGLShaderProgram,
        QOpenGLTexture,
        QPixmap,
        QSurfaceFormat,
        QTransform,
        QVector2D,
        QVector4D,
        )

from PyQt5.QtWidgets import (
        QApplication, 
        QGridLayout,
        QHBoxLayout,
        QMainWindow,
        QOpenGLWidget,
        QWidget,
        )

from PyQt5.QtCore import (
        QFileInfo,
        QPointF,
        QSize,
        QTimer,
        )

import numpy as np
import cv2
from utils import Utils

from data_window import DataWindow


class FragmentVao:
    def __init__(self, fragment_view, fragment_program, gl):
        self.fragment_view = fragment_view
        self.gl = gl
        self.vao = None
        self.vao_modified = ""
        self.fragment_program = fragment_program
        self.getVao()

    def getVao(self):
        if self.vao_modified >= self.fragment_view.modified:
            return self.vao

        self.fragment_program.bind()

        if self.vao is None:
            self.vao = QOpenGLVertexArrayObject()
            self.vao.create()

        self.vao.bind()

        self.vbo = QOpenGLBuffer()
        self.vbo.create()
        self.vbo.bind()
        fv = self.fragment_view
        pts3d = np.ascontiguousarray(fv.vpoints[:,:3], dtype=np.float32)

        nbytes = pts3d.size*pts3d.itemsize
        self.vbo.allocate(pts3d, nbytes)

        vloc = self.fragment_program.attributeLocation("position")
        print("vloc", vloc)
        f = self.gl
        f.glVertexAttribPointer(
                vloc,
                pts3d.shape[1], int(f.GL_FLOAT), int(f.GL_FALSE), 
                0, 0)
        self.vbo.release()

        self.fragment_program.enableAttributeArray(vloc)

        self.ibo = QOpenGLBuffer(QOpenGLBuffer.IndexBuffer)
        self.ibo.create()
        self.ibo.bind()

        # TODO: Need to deal with case where we have a
        # a line, not a triangulated surface!
        # notice that indices must be uint8, uint16, or uint32
        fv_trgls = fv.trgls()
        if fv_trgls is None:
            fv_trgls = np.zeros((0,3), dtype=np.uint32)
        
        trgls = np.ascontiguousarray(fv_trgls, dtype=np.uint32)

        self.trgl_index_size = trgls.size

        nbytes = trgls.size*trgls.itemsize
        self.ibo.allocate(trgls, nbytes)

        print("nodes, trgls", pts3d.shape, trgls.shape)

        self.vao_modified = Utils.timestamp()
        self.vao.release()
        
        # do not release ibo before vao is released!
        self.ibo.release()

        return self.vao


class GLDataWindow(DataWindow):
    def __init__(self, window, axis):
        super(GLDataWindow, self).__init__(window, axis)
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)
        self.glw = GLDataWindowChild(self)
        layout.addWidget(self.glw)

    def drawSlice(self):
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
      uniform sampler2D overlay_sampler;
      uniform sampler2D fragments_sampler;
      uniform float frag_opacity = 1.;
      in vec2 ftxt;
      out vec4 fColor;

      void main()
      {
        fColor = texture(base_sampler, ftxt);
        vec4 frColor = texture(fragments_sampler, ftxt);
        // float alpha = frColor.a;
        float alpha = frag_opacity*frColor.a;
        fColor = (1.-alpha)*fColor + alpha*frColor;
        vec4 oColor = texture(overlay_sampler, ftxt);
        alpha = oColor.a;
        fColor = (1.-alpha)*fColor + alpha*oColor;
      }
    ''',
}

fragment_code = {
    "name": "fragment",

    "vertex": '''
      #version 410 core

      uniform mat4 xform;
      in vec3 position;
      void main() {
        gl_Position = xform*vec4(position, 1.0);
      }
    ''',

    # modified from https://stackoverflow.com/questions/16884423/geometry-shader-producing-gaps-between-lines/16886843
    "geometry": '''
      #version 410 core
  
      uniform float thickness;
      uniform vec2 window_size;
  
      layout(triangles) in;
      layout(triangle_strip, max_vertices = 18) out;
  
      const float angles[] = float[8](
        radians(0), radians(45), radians(90), radians(135), 
        radians(180), radians(225), radians(270), radians(315));
      const vec2 trig_table[] = vec2[9](
        vec2(cos(angles[0]), sin(angles[0])),
        vec2(cos(angles[1]), sin(angles[1])),
        vec2(cos(angles[2]), sin(angles[2])),
        vec2(cos(angles[3]), sin(angles[3])),
        vec2(cos(angles[4]), sin(angles[4])),
        vec2(cos(angles[5]), sin(angles[5])),
        vec2(cos(angles[6]), sin(angles[6])),
        vec2(cos(angles[7]), sin(angles[7])),
        vec2(0., 0.));
  
  
      void main()
      {
        float dist[3];
        float sgn[3]; // sign(float) returns float
        float sig = 0; // signature
        float m = 1;

        for (int i=0; i<3; i++) {
          dist[i] = gl_in[i].gl_Position.z;
          sgn[i] = sign(dist[i]);
          sig += m*(1+sgn[i]);
          m *= 3;
        }

        // These correspond to the cases where there are
        // no intersections (---, 000, +++):
        if (sig == 0 || sig == 13 || sig == 26) return;
  
        // Have to go through nodes in the correct order.
        // Imagine a triangle a,b,c, with distances
        // a = -1, b = 0, c = 1.  In this case, there
        // are two intersections: one at point b, and one on
        // the line between a and c.
        // All three lines (ab, bc, ca) will have intersections,
        // the lines ab and bc will both have the same intersection,
        // at point b.
        // If the lines are scanned in that order, and only the first
        // two detected intersections are stored, then the two detected
        // intersections will both be point b!
        // There are various ways to detect and avoid this problem,
        // but the method below seems the least convoluted.

        // General note: much of the code below could be replaced with
        // a lookup table based on the sig (signature) computed above.
        // This rewrite can wait until a later time, though, since 
        // the existing code works, and seems fast enough.
        
        ivec3 ijk = ivec3(0, 1, 2); // use swizzle to permute the indices

        // Let each vertex of the triangle be denoted by +, -, or 0,
        // depending on the sign (sgn) of its distance from the plane.
        // 
        // We want to rotate any given triangle so that
        // its ordered sgn values match one of these:
        // ---  000  +++  (no intersections)
        // 0++  -0-       (one intersection)
        // 0+0  -00       (two intersections)
        // 0+-  -+0       (two intersections)
        // -++  -+-       (two intersections)
        // Every possible triangle can be cyclically reordered into
        // one of these orderings.
        // In the two-intersection cases above, the intersections
        // computed from the first two segments (ignoring 00 segments)
        // will be unique, and in a consistent orientation,
        // given these orderings.
        // In most cases, the test sgn[ijk.x] < sgn[ijk.y] is
        // sufficient to ensure this order.  But there is
        // one ambiguous case: 0+- and -0+ are two orderings
        // of the same triangle, and both pass the test.
        // But only the 0+- ordering will allow the first two
        // segments to yield two intersections in the correct order
        // (the -0+ ordering will yield the same location twice!).
        // So an additional test is needed to avoid this case:
        // sgn[ijk.y] >= sgn[ijk.z]
        // Thus the input triangle needs to be rotated until
        // the following condition holds:
        // sgn[ijk.x] < sgn[ijk.y] && sgn[ijk.y] >= sgn[ijk.z]
        // So the condition for continuing to rotate is that the
        // condition above not be true, in other words:
        // !(sgn[ijk.x] < sgn[ijk.y] && sgn[ijk.y] >= sgn[ijk.z])
        // Rewrite, so the condition to continue to rotate is:
        // sgn[ijk.x] >= sgn[ijk.y] || sgn[ijk.y] < sgn[ijk.z]>0;

        // Continue to rotate the triangle so long as the above condition is
        // met:
        for (int i=0; 
             i<3 // stop after 3 iterations
             && (sgn[ijk.x] >= sgn[ijk.y] || sgn[ijk.y] < sgn[ijk.z]);
             ijk=ijk.yzx, i++);
        // At this point, ijk has been set to rotate the triangle 
        // to the correct order.

        vec4 pcs[2];
        int j = 0;
        for (int i=0; i<3 && j<2; ijk=ijk.yzx, i++) {
          float da = dist[ijk.x];
          float db = dist[ijk.y];
          if (da*db > 0 || (da == 0 && db == 0)) continue;
  
          vec4 pa = gl_in[ijk.x].gl_Position;
          vec4 pb = gl_in[ijk.y].gl_Position;
          float fa = abs(da);
          float fb = abs(db);
          vec4 pc = pa;
          if (fa > 0 || fb > 0) pc = (fa * pb + fb * pa) / (fa + fb);
          pcs[j++] = pc;
        }

        if (j<2) return;
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
        vec2 factor = thickness*vec2(1./window_size.x, 1./window_size.y);
        vec4 offsets[9];
        for (int i=0; i<9; i++) {
          // trig contains cosine and sine of angle i*45 degrees
          vec2 trig = trig_table[i];
          vec2 raw_offset = -trig.x*tan + trig.y*norm;
          vec4 scaled_offset = vec4(factor*raw_offset, 0., 0.);
          offsets[i] = scaled_offset;
        }

        // all arrays need to be the same size
        // so the correct one can be copied into "vs"
        ivec2 v18[] = ivec2[18](
          ivec2(0, 8),
          ivec2(0, 6),
          ivec2(0, 7),
          ivec2(0, 8),
          ivec2(0, 0),
          ivec2(0, 1),
          ivec2(0, 8),
          ivec2(0, 2),
          ivec2(1, 8),
          ivec2(1, 2),
          ivec2(1, 3),
          ivec2(1, 8),
          ivec2(1, 4),
          ivec2(1, 5),
          ivec2(1, 8),
          ivec2(1, 6),
          ivec2(0, 8),
          ivec2(0, 6)
        );
        ivec2 v10[] = ivec2[18](
          ivec2(0, 0),
          ivec2(0, 1),
          ivec2(0, 7),
          ivec2(0, 2),
          ivec2(0, 6),
          ivec2(1, 2),
          ivec2(1, 6),
          ivec2(1, 3),
          ivec2(1, 5),
          ivec2(1, 4),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1)
        );
        ivec2 v4[] = ivec2[18](
          ivec2(0, 2),
          ivec2(0, 6),
          ivec2(1, 2),
          ivec2(1, 6),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1),
          ivec2(-1, -1)
        );
        ivec2 vs[18];
        if (vcount == 18) {
          vs = v18;
        } else if (vcount == 10) {
          vs = v10;
        } else if (vcount == 4) {
          vs = v4;
        }

        for (int i=0; i<vcount; i++) {
          ivec2 iv = vs[i];
          gl_Position = pcs[iv.x] + offsets[iv.y];
          EmitVertex();
        }
      }
    ''',

    "fragment": '''
      #version 410 core

      uniform vec4 gcolor;
      uniform vec4 icolor;
      out vec4 fColor;

      void main()
      {
        fColor = gcolor;
      }
    ''',
}

"""
borders_code = {
    "name": "borders",
    "vertex": '''
      #version 410 core

      in vec2 position;
      void main() {
        gl_Position = vec4(position, 0.0, 1.0);
      }
    ''',
    "fragment": '''
      #version 410 core

      uniform vec4 color;
      out vec4 fColor;

      void main()
      {
        fColor = color;
      }
    ''',
}
"""

class GLDataWindowChild(QOpenGLWidget):
    def __init__(self, gldw, parent=None):
        super(GLDataWindowChild, self).__init__(parent)
        self.gldw = gldw
        self.setMouseTracking(True)
        self.fragment_vaos = {}
        self.multi_fragment_vao = None
        # 0: asynchronous mode, 1: synch mode
        # synch mode is much slower
        self.logging_mode = 1
        # self.logging_mode = 0

    def dwKeyPressEvent(self, e):
        self.gldw.dwKeyPressEvent(e)

    def initializeGL(self):
        print("initializeGL")
        self.context().aboutToBeDestroyed.connect(self.destroyingContext)
        self.gl = self.context().versionFunctions()
        self.main_context = self.context()
        # Note that debug logging only takes place if the
        # surface format option "DebugContext" is set
        self.logger = QOpenGLDebugLogger()
        self.logger.initialize()
        self.logger.messageLogged.connect(lambda m: self.onLogMessage("dc", m))
        self.logger.startLogging(self.logging_mode)
        msg = QOpenGLDebugMessage.createApplicationMessage("test debug messaging")
        self.logger.logMessage(msg)
        self.buildPrograms()
        self.buildSliceVao()
        # self.buildBordersVao()

        # self.createGLSurfaces()
        
        f = self.gl
        # self.gl.glClearColor(.3,.6,.3,1.)
        f.glClearColor(.6,.3,.3,1.)

    def resizeGL(self, width, height):
        # print("resize", width, height)
        # based on https://stackoverflow.com/questions/59338015/minimal-opengl-offscreen-rendering-using-qt
        vp_size = QSize(width, height)
        fbo_format = QOpenGLFramebufferObjectFormat()
        fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        f = self.gl
        fbo_format.setInternalTextureFormat(f.GL_RGBA16)
        self.fragment_fbo = QOpenGLFramebufferObject(vp_size, fbo_format)
        self.fragment_fbo.bind()
        # TODO: create "pick" texture, attach it to fragment_fbo
        f.glViewport(0, 0, vp_size.width(), vp_size.height())

        QOpenGLFramebufferObject.bindDefault()

    def paintGL(self):
        # print("paintGL")
        volume_view = self.gldw.volume_view
        if volume_view is None :
            return
        
        f = self.gl
        f.glClearColor(.6,.3,.3,1.)
        f.glClear(f.GL_COLOR_BUFFER_BIT)
        self.paintSlice()

    # assumes the image is from fragment_fbo, and that
    # fragment_fbo was created with the RGBA16 format
    def npArrayFromQImage(im):
        # Because fragment_fbo was created with an
        # internal texture format of RGBA16 (see the code
        # where fragment_fbo was created), the QImage
        # created by toImage is in QImage format 27, which is 
        # "a premultiplied 64-bit halfword-ordered RGBA format (16-16-16-16)"
        # The "premultiplied" means that the RGB values have already
        # been multiplied by alpha.
        # This comment is based on:
        # https://doc.qt.io/qt-5/qimage.html
        # https://doc.qt.io/qt-5/qopenglframebufferobject.html
        im = self.fragment_fbo.toImage()
        # print("image format, size", im.format(), im.size(), im.sizeInBytes())
        # im.save("test.png")

        # conversion to numpy array based on
        # https://stackoverflow.com/questions/19902183/qimage-to-numpy-array-using-pyside
        iw = im.width()
        ih = im.height()
        iptr = im.constBits()
        iptr.setsize(im.sizeInBytes())
        arr = np.frombuffer(iptr, dtype=np.uint16)
        arr.resize(ih, iw, 4)
        return arr

    def drawFragments(self):
        # print("entering draw fragments")
        timera = Utils.Timer()
        timera.active = False
        self.fragment_fbo.bind()
        f = self.gl

        # Be sure to clear with alpha = 0
        # so that the slice view isn't blocked!
        f.glClearColor(0.,0.,0.,0.)
        f.glClear(f.GL_COLOR_BUFFER_BIT)

        # Aargh!  PyQt5 does not define glClearBufferfv!!
        # f.glClearBufferfv(f.GL_COLOR, 0, (.3, .6, .3, 1.))

        dw = self.gldw
        axstr = "(%d) "%dw.axis
        ww = dw.size().width()
        wh = dw.size().height()
        opacity = dw.getDrawOpacity("overlay")
        apply_line_opacity = dw.getDrawApplyOpacity("line")
        line_alpha = 1.
        if apply_line_opacity:
            line_alpha = opacity
        thickness = dw.getDrawWidth("line")
        thickness = (3*thickness)//2
        volume_view = dw.volume_view
        xform = QMatrix4x4()

        iind = dw.iIndex
        jind = dw.jIndex
        kind = dw.kIndex
        zoom = dw.getZoom()
        cijk = volume_view.ijktf

        # Convert tijk coordinates to OpenGL clip-window coordinates.
        # Note that the matrix converts the axis coordinate such that
        # only points within .5 voxel widths on either side are
        # in the clip-window range -1. < z < 1.
        mat = np.zeros((4,4), dtype=np.float32)
        ww = dw.size().width()
        wh = dw.size().height()
        wf = zoom/(.5*ww)
        hf = zoom/(.5*wh)
        df = 1/.5
        mat[0][iind] = wf
        mat[0][3] = -wf*cijk[iind]
        mat[1][jind] = -hf
        mat[1][3] = hf*cijk[jind]
        mat[2][kind] = df
        mat[2][3] = -df*cijk[kind]
        mat[3][3] = 1.
        xform = QMatrix4x4(mat.flatten().tolist())

        '''
        for i in range(4):
            print(xform.row(i))
        '''
        self.fragment_program.bind()
        self.fragment_program.setUniformValue("xform", xform)
        self.fragment_program.setUniformValue("window_size", dw.size())
        self.fragment_program.setUniformValue("thickness", 1.*thickness)

        timera.time(axstr+"setup")
        new_fragment_vaos = {}
        iindex = 0
        for fv in dw.fragmentViews():
            if not fv.visible:
                continue
            qcolor = fv.fragment.color
            rgba = list(qcolor.getRgbF())
            rgba[3] = 1.
            iindex += 1
            findex = iindex/65536.
            self.fragment_program.setUniformValue("gcolor", *rgba)
            self.fragment_program.setUniformValue("icolor", *rgba)
            if fv not in self.fragment_vaos:
                fvao = FragmentVao(fv, self.fragment_program, self.gl)
                self.fragment_vaos[fv] = fvao
            fvao = self.fragment_vaos[fv]
            new_fragment_vaos[fv] = fvao
            vao = fvao.getVao()
            vao.bind()

            f.glDrawElements(f.GL_TRIANGLES, fvao.trgl_index_size, 
                             f.GL_UNSIGNED_INT, None)
            vao.release()
        timera.time(axstr+"draw")
        self.fragment_vaos = new_fragment_vaos
        self.fragment_program.release()
        QOpenGLFramebufferObject.bindDefault()
        # print("leaving drawFragments")

    def texFromData(self, data, qiformat):
        bytesperline = (data.size*data.itemsize)//data.shape[0]
        img = QImage(data, data.shape[1], data.shape[0],
                     bytesperline, qiformat)
        # mirror image vertically because of different y direction conventions
        tex = QOpenGLTexture(img.mirrored(), 
                             QOpenGLTexture.DontGenerateMipMaps)
        tex.setWrapMode(QOpenGLTexture.DirectionS, 
                        QOpenGLTexture.ClampToBorder)
        tex.setWrapMode(QOpenGLTexture.DirectionT, 
                        QOpenGLTexture.ClampToBorder)
        tex.setMagnificationFilter(QOpenGLTexture.Nearest)
        return tex

    def drawOverlays(self, data):
        dw = self.gldw
        volume_view = dw.volume_view

        ww = dw.size().width()
        wh = dw.size().height()
        opacity = dw.getDrawOpacity("overlay")
        bw = dw.getDrawWidth("borders")
        if bw > 0:
            bwh = (bw-1)//2
            axis_color = dw.axisColor(dw.axis)
            alpha = 1.
            if dw.getDrawApplyOpacity("borders"):
                alpha = opacity
            alpha16 = int(alpha*65535)
            axis_color[3] = alpha16
            cv2.rectangle(data, (bwh,bwh), (ww-bwh-1,wh-bwh-1), axis_color, bw)
            cv2.rectangle(data, (0,0), (ww-1,wh-1), (0,0,0,alpha*65535), 1)
        aw = dw.getDrawWidth("axes")
        if aw > 0:
            axis_color = dw.axisColor(dw.axis)
            fij = dw.tijkToIj(volume_view.ijktf)
            fx,fy = dw.ijToXy(fij)
            alpha = 1.
            if dw.getDrawApplyOpacity("axes"):
                alpha = opacity
            alpha16 = int(alpha*65535)
            icolor = dw.axisColor(dw.iIndex)
            icolor[3] = alpha16
            cv2.line(data, (fx,0), (fx,wh), icolor, aw)
            jcolor = dw.axisColor(dw.jIndex)
            jcolor[3] = alpha16
            cv2.line(data, (0,fy), (ww,fy), jcolor, aw)
        lw = dw.getDrawWidth("labels")
        alpha = 1.
        if dw.getDrawApplyOpacity("labels"):
            alpha = opacity
        alpha16 = int(alpha*65535)
        dww = dw.window
        if dww.getVolBoxesVisible():
            cur_vol_view = dww.project_view.cur_volume_view
            cur_vol = dww.project_view.cur_volume
            for vol, vol_view in dww.project_view.volumes.items():
                if vol == cur_vol:
                    continue
                gs = vol.corners()
                minxy, maxxy, intersects_slice = dw.cornersToXY(gs)
                if not intersects_slice:
                    continue
                color = vol_view.cvcolor
                color[3] = alpha16
                cv2.rectangle(outrgbx, minxy, maxxy, color, 2)
        tiff_corners = dww.tiff_loader.corners()
        if tiff_corners is not None:
            # print("tiff corners", tiff_corners)

            minxy, maxxy, intersects_slice = dw.cornersToXY(tiff_corners)
            if intersects_slice:
                # tcolor is a string
                tcolor = dww.tiff_loader.color()
                qcolor = QColor(tcolor)
                rgba = qcolor.getRgbF()
                cvcolor = [int(65535*c) for c in rgba]
                cvcolor[3] = alpha16
                cv2.rectangle(outrgbx, minxy, maxxy, cvcolor, 2)
        
        if lw > 0:
            label = dw.sliceGlobalLabel()
            gpos = dw.sliceGlobalPosition()
            # print("label", self.axis, label, gpos)
            txt = "%s: %d" % (label, gpos)
            org = (10,20)
            size = 1.
            m = 16000
            gray = (m,m,m,alpha16)
            white = (65535,65535,65535,alpha16)
            
            cv2.putText(data, txt, org, cv2.FONT_HERSHEY_PLAIN, size, gray, 3)
            cv2.putText(data, txt, org, cv2.FONT_HERSHEY_PLAIN, size, white, 1)
            dw.drawScaleBar(data, alpha16)
            dw.drawTrackingCursor(data, alpha16)
                

    def paintSlice(self):
        dw = self.gldw
        volume_view = dw.volume_view
        f = self.gl
        self.slice_program.bind()

        # viewing window width
        ww = self.size().width()
        wh = self.size().height()
        # viewing window half width
        whw = ww//2
        whh = wh//2

        data_slice = np.zeros((wh,ww), dtype=np.uint16)
        zarr_max_width = self.gldw.getZarrMaxWidth()
        paint_result = volume_view.paintSlice(
                data_slice, self.gldw.axis, volume_view.ijktf, 
                self.gldw.getZoom(), zarr_max_width)

        base_tex = self.texFromData(data_slice, QImage.Format_Grayscale16)
        bloc = self.slice_program.uniformLocation("base_sampler")
        if bloc < 0:
            print("couldn't get loc for base sampler")
            return
        # print("bloc", bloc)
        bunit = 1
        f.glActiveTexture(f.GL_TEXTURE0+bunit)
        base_tex.bind()
        self.slice_program.setUniformValue(bloc, bunit)

        overlay_data = np.zeros((wh,ww,4), dtype=np.uint16)
        self.drawOverlays(overlay_data)
        overlay_tex = self.texFromData(overlay_data, QImage.Format_RGBA64)
        oloc = self.slice_program.uniformLocation("overlay_sampler")
        if oloc < 0:
            print("couldn't get loc for overlay sampler")
            return
        ounit = 2
        f.glActiveTexture(f.GL_TEXTURE0+ounit)
        overlay_tex.bind()
        self.slice_program.setUniformValue(oloc, ounit)

        self.drawFragments()

        self.slice_program.bind()
        floc = self.slice_program.uniformLocation("fragments_sampler")
        if floc < 0:
            print("couldn't get loc for fragments sampler")
            return
        funit = 3
        f.glActiveTexture(f.GL_TEXTURE0+funit)
        tex_ids = self.fragment_fbo.textures()
        # print("textures", tex_ids)
        fragments_tex_id = tex_ids[0]
        f.glBindTexture(f.GL_TEXTURE_2D, fragments_tex_id)
        self.slice_program.setUniformValue(floc, funit)

        opacity = dw.getDrawOpacity("overlay")
        apply_line_opacity = dw.getDrawApplyOpacity("line")
        line_alpha = 1.
        if apply_line_opacity:
            line_alpha = opacity
        self.slice_program.setUniformValue("frag_opacity", line_alpha)

        f.glActiveTexture(f.GL_TEXTURE0)
        vaoBinder = QOpenGLVertexArrayObject.Binder(self.slice_vao)
        self.slice_program.bind()
        f.glDrawElements(f.GL_TRIANGLES, 
                         self.slice_indices.size, f.GL_UNSIGNED_INT, None)
        self.slice_program.release()
        vaoBinder = None

    def closeEvent(self, e):
        print("glw widget close event")

    def destroyingContext(self):
        print("glw destroying context")

    def onLogMessage(self, head, msg):
        print(head, "log:", msg.message())

    def buildProgram(self, sdict):
        edict = {
            "vertex": QOpenGLShader.Vertex,
            "fragment": QOpenGLShader.Fragment,
            "geometry": QOpenGLShader.Geometry,
            "tessellation_control": QOpenGLShader.TessellationControl,
            "tessellation_evaluation": QOpenGLShader.TessellationEvaluation,
            }
        name = sdict["name"]
        program = QOpenGLShaderProgram()
        for key, code in sdict.items():
            if key not in edict:
                continue
            enum = edict[key]
            ok = program.addShaderFromSourceCode(enum, code)
            if not ok:
                print(name, key, "shader failed")
                exit()
        ok = program.link()
        if not ok:
            print(name, "link failed")
            exit()
        return program

    def buildPrograms(self):
        self.slice_program = self.buildProgram(slice_code)
        # self.borders_program = self.buildProgram(borders_code)
        self.fragment_program = self.buildProgram(fragment_code)

    def buildSliceVao(self):
        self.slice_vao = QOpenGLVertexArrayObject()
        self.slice_vao.create()

        vloc = self.slice_program.attributeLocation("position")
        # print("vloc", vloc)
        tloc = self.slice_program.attributeLocation("vtxt")
        # print("tloc", tloc)

        self.slice_program.bind()

        f = self.gl

        vaoBinder = QOpenGLVertexArrayObject.Binder(self.slice_vao)

        # defaults to type=VertexBuffer, usage_pattern = Static Draw
        vbo = QOpenGLBuffer()
        vbo.create()
        vbo.bind()

        xyuvs_list = [
                ((-1, +1), (0., 1.)),
                ((+1, -1), (1., 0.)),
                ((-1, -1), (0., 0.)),
                ((+1, +1), (1., 1.)),
                ]
        xyuvs = np.array(xyuvs_list, dtype=np.float32)

        nbytes = xyuvs.size*xyuvs.itemsize
        # allocates space and writes xyuvs into vbo;
        # requires that vbo be bound
        vbo.allocate(xyuvs, nbytes)
        
        f.glVertexAttribPointer(
                vloc,
                xyuvs.shape[1], int(f.GL_FLOAT), int(f.GL_FALSE), 
                4*xyuvs.itemsize, 0)
        f.glVertexAttribPointer(
                tloc, 
                xyuvs.shape[1], int(f.GL_FLOAT), int(f.GL_FALSE), 
                4*xyuvs.itemsize, 2*xyuvs.itemsize)
        vbo.release()
        self.slice_program.enableAttributeArray(vloc)
        self.slice_program.enableAttributeArray(tloc)
        # print("enabled")

        # https://stackoverflow.com/questions/8973690/vao-and-element-array-buffer-state
        # Qt's name for GL_ELEMENT_ARRAY_BUFFER
        ibo = QOpenGLBuffer(QOpenGLBuffer.IndexBuffer)
        ibo.create()
        # print("ibo", ibo.bufferId())
        ibo.bind()

        indices_list = [(0,1,2), (1,0,3)]
        # notice that indices must be uint8, uint16, or uint32
        self.slice_indices = np.array(indices_list, dtype=np.uint32)
        nbytes = self.slice_indices.size*self.slice_indices.itemsize
        ibo.allocate(self.slice_indices, nbytes)

        # Order is important in next 2 lines.
        # Setting vaoBinder to None unbinds (releases) vao.
        # If ibo is unbound before vao is unbound, then
        # ibo will be detached from vao.  We don't want that!
        vaoBinder = None
        ibo.release()


