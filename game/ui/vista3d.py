"""La pista in 3D, disegnata con OpenGL dentro alla finestra di pygame.

Il resto del gioco resta com'e': pannelli, tabellone e pulsanti li disegna
pygame, come sempre. La scena 3D si disegna fuori schermo, in un buffer della
scheda video, e se ne legge il risultato come un'immagine qualunque che poi si
incolla nel riquadro della mappa. Costa una lettura dalla scheda video per
fotogramma - un paio di millisecondi su un PC - e in cambio non obbliga a
riscrivere tutta la grafica per OpenGL.

Se OpenGL non c'e' - la versione web, un PC senza driver, `moderngl` non
installato - `disponibile()` risponde di no e chi disegna la gara resta sulla
mappa 2D di sempre. Niente si rompe.

Le macchine restano 2D apposta: sono sagome piatte appoggiate sull'asfalto,
girate nel verso di marcia, che la scheda video mette in prospettiva insieme
al resto - cosi' una collina o una tribuna le nasconde quando devono.
"""
from __future__ import annotations

import math
import sys
from array import array

import pygame

from . import pista3d

try:
    import moderngl
except Exception:            # non installato, o nel browser
    moderngl = None

_CTX = None
_STATO = None                # None: non ancora provato


def disponibile() -> bool:
    """C'e' una scheda video con cui disegnare in 3D? Si prova una volta sola."""
    global _CTX, _STATO
    if _STATO is not None:
        return _STATO
    _STATO = False
    if moderngl is None or sys.platform == "emscripten":
        return False
    for opzioni in ({}, {"backend": "egl"}):
        try:
            _CTX = moderngl.create_standalone_context(require=330, **opzioni)
        except Exception:
            continue
        _STATO = True
        break
    return _STATO


def spegni() -> None:
    """Dopo un errore della scheda video non si riprova: si resta sul 2D."""
    global _STATO
    _STATO = False


# --------------------------------------------------------------- matrici
def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _prospettiva(fov_y: float, aspetto: float, vicino: float, lontano: float) -> list:
    f = 1.0 / math.tan(math.radians(fov_y) / 2.0)
    return [f / aspetto, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (lontano + vicino) / (vicino - lontano), -1,
            0, 0, 2 * lontano * vicino / (vicino - lontano), 0]


def _guarda(occhio, bersaglio) -> list:
    f = _norm((bersaglio[0] - occhio[0], bersaglio[1] - occhio[1], bersaglio[2] - occhio[2]))
    s = _norm(_cross(f, (0.0, 1.0, 0.0)))
    u = _cross(s, f)
    return [s[0], u[0], -f[0], 0,
            s[1], u[1], -f[1], 0,
            s[2], u[2], -f[2], 0,
            -_dot(s, occhio), -_dot(u, occhio), _dot(f, occhio), 1]


def _per(a: list, b: list) -> list:
    """a * b, tutte e due per colonne come le vuole OpenGL."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _inversa(m: list) -> list:
    """Inversa di una 4x4 per colonne (Gauss-Jordan: la si fa una volta a fotogramma)."""
    a = [[m[c * 4 + r] for c in range(4)] + [1.0 if r == k else 0.0 for k in range(4)]
         for r in range(4)]
    for c in range(4):
        p = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        d = a[c][c] or 1e-12
        a[c] = [x / d for x in a[c]]
        for r in range(4):
            if r != c:
                k = a[r][c]
                a[r] = [x - k * y for x, y in zip(a[r], a[c])]
    return [a[r][4 + c] for c in range(4) for r in range(4)]


# ---------------------------------------------------------------- shader
_VS_MONDO = """
#version 330
uniform mat4 mvp;
uniform vec3 eye;
in vec3 in_pos; in vec3 in_nor; in vec3 in_col; in float in_glow;
out vec3 v_nor; out vec3 v_col; out float v_glow; out vec3 v_pos;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_nor = in_nor; v_col = in_col; v_glow = in_glow;
    v_pos = in_pos;
}
"""

_FS_MONDO = """
#version 330
uniform vec3 sun; uniform vec3 sun_col; uniform vec3 amb_sky; uniform vec3 amb_ground;
uniform vec3 fog_col; uniform float fog_d; uniform float fari; uniform vec3 eye;
in vec3 v_nor; in vec3 v_col; in float v_glow; in vec3 v_pos;
out vec4 frag;
void main() {
    // la distanza si misura qui e non nei vertici: la pianura attorno e' un
    // solo quadrato da decine di chilometri, e interpolata dai suoi angoli
    // sarebbe tutta nebbia
    float v_dist = length(v_pos - eye);
    vec3 n = normalize(v_nor);
    float d = max(dot(n, sun), 0.0);
    vec3 amb = mix(amb_ground, amb_sky, n.y * 0.5 + 0.5);
    vec3 c = v_col * (amb + sun_col * d);
    c += v_col * v_glow * fari * vec3(1.0, 0.88, 0.66);
    float f = 1.0 - exp(-pow(v_dist / fog_d, 1.7));
    frag = vec4(mix(c, fog_col, clamp(f, 0.0, 1.0)), 1.0);
}
"""

_VS_CIELO = """
#version 330
in vec2 in_ndc;
out vec2 v_ndc;
void main() { v_ndc = in_ndc; gl_Position = vec4(in_ndc, 0.9999, 1.0); }
"""

_FS_CIELO = """
#version 330
uniform mat4 inv_vp; uniform vec3 eye; uniform vec3 zenit; uniform vec3 orizzonte;
uniform vec3 sun; uniform vec3 sun_col;
in vec2 v_ndc;
out vec4 frag;
void main() {
    vec4 p = inv_vp * vec4(v_ndc, 1.0, 1.0);
    vec3 dir = normalize(p.xyz / p.w - eye);
    float h = clamp(dir.y, 0.0, 1.0);
    vec3 c = mix(orizzonte, zenit, pow(h, 0.55));
    float s = max(dot(dir, sun), 0.0);
    c += sun_col * (pow(s, 900.0) * 1.2 + pow(s, 12.0) * 0.12);
    frag = vec4(c, 1.0);
}
"""

_VS_AUTO = """
#version 330
uniform mat4 mvp; uniform vec3 eye; uniform float k_scala; uniform float ombra;
uniform vec3 sun;
in vec2 in_corner;
in vec3 i_pos; in vec3 i_fwd; in vec3 i_col; in float i_sel;
out vec2 v_uv; out vec3 v_col; out float v_dist; out float v_sel;
void main() {
    // lontano dalla camera la sagoma si ingrandisce: una macchina vera, vista
    // da un elicottero a tre chilometri, e' un puntino da mezzo pixel
    float m = max(1.0, length(i_pos - eye) / k_scala);
    vec3 f = normalize(i_fwd);
    vec3 r = normalize(cross(f, vec3(0.0, 1.0, 0.0)));
    vec3 u = cross(r, f);
    vec3 p = i_pos + f * in_corner.x * 5.6 * m + r * in_corner.y * 2.4 * m;
    if (ombra > 0.5) {
        p += u * 0.10 * m;
        p.xz -= sun.xz * 0.45 * m;
    } else {
        p += u * 0.30 * m;
    }
    gl_Position = mvp * vec4(p, 1.0);
    v_uv = vec2(in_corner.x + 0.5, in_corner.y + 0.5);
    v_col = i_col; v_sel = i_sel;
    v_dist = length(i_pos - eye);
}
"""

_FS_AUTO = """
#version 330
uniform sampler2D tex; uniform float ombra;
uniform vec3 sun_col; uniform vec3 amb_sky; uniform vec3 fog_col; uniform float fog_d;
uniform float fari;
in vec2 v_uv; in vec3 v_col; in float v_dist; in float v_sel;
out vec4 frag;
void main() {
    vec4 t = texture(tex, v_uv);
    if (t.a < 0.5) discard;
    if (ombra > 0.5) { frag = vec4(0.0, 0.0, 0.0, 0.30); return; }
    vec3 c = mix(vec3(t.g), v_col * (0.30 + t.g), t.r);
    c *= amb_sky + sun_col * 0.85 + vec3(fari * 0.55);
    c = mix(c, vec3(1.0), v_sel * 0.18);
    float f = 1.0 - exp(-pow(v_dist / fog_d, 1.7));
    frag = vec4(mix(c, fog_col, clamp(f, 0.0, 1.0) * 0.8), 1.0);
}
"""


def _sagoma() -> pygame.Surface:
    """La macchina vista da sopra, col muso verso destra.

    Non e' un'immagine a colori: nel rosso c'e' "quanto e' colore di
    squadra", nel verde la luminosita'. Lo shader la tinge per ognuno.
    """
    s = pygame.Surface((128, 56), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    squadra = (255, 200, 0, 255)
    scuro = (0, 38, 0, 255)
    gomma = (0, 22, 0, 255)
    pygame.draw.rect(s, scuro, (2, 5, 11, 46), border_radius=2)          # ala dietro
    pygame.draw.rect(s, gomma, (13, 3, 19, 12), border_radius=3)         # gomme dietro
    pygame.draw.rect(s, gomma, (13, 41, 19, 12), border_radius=3)
    pygame.draw.rect(s, gomma, (84, 5, 16, 10), border_radius=3)         # gomme davanti
    pygame.draw.rect(s, gomma, (84, 41, 16, 10), border_radius=3)
    pygame.draw.polygon(s, squadra, [(12, 20), (40, 17), (80, 23), (118, 26),
                                     (118, 30), (80, 33), (40, 39), (12, 36)])
    pygame.draw.ellipse(s, squadra, (30, 12, 44, 32))                   # pance
    pygame.draw.rect(s, squadra, (108, 8, 14, 40), border_radius=2)      # ala davanti
    pygame.draw.ellipse(s, (0, 26, 0, 255), (56, 22, 18, 12))            # abitacolo
    pygame.draw.circle(s, (0, 235, 0, 255), (64, 28), 4)                 # casco
    return s


class Elicottero:
    """La ripresa dall'alto: gira da sola piano, finche' non la si prende."""

    def __init__(self):
        self.yaw = math.radians(215)
        self.pitch = math.radians(46)
        self.zoom = 1.0
        self.fermo = 0.0

    def aggiorna(self, dt: float) -> None:
        if self.fermo > 0:
            self.fermo -= dt
        else:
            self.yaw += dt * math.radians(1.5)

    def trascina(self, dx: float, dy: float) -> None:
        self.yaw += dx * 0.006
        self.pitch = max(math.radians(12), min(math.radians(84), self.pitch + dy * 0.004))
        self.fermo = 10.0

    def rotella(self, y: float) -> None:
        self.zoom = max(0.22, min(2.2, self.zoom * (0.88 ** y)))
        self.fermo = 10.0

    def inquadra(self, geo, aspetto: float = 1.5, fov: float = 38.0) -> tuple:
        bersaglio = (geo.cx, geo.cy, geo.cz)
        # abbastanza lontano che il circuito ci stia tutto anche in un
        # riquadro stretto: si guarda il lato piu' corto dell'inquadratura
        mezzo = math.tan(math.radians(fov) / 2.0) * min(aspetto, 1.3)
        dist = geo.span * 0.78 / mezzo * self.zoom
        cp = math.cos(self.pitch)
        occhio = (bersaglio[0] - math.cos(self.yaw) * cp * dist,
                  bersaglio[1] + math.sin(self.pitch) * dist,
                  bersaglio[2] - math.sin(self.yaw) * cp * dist)
        return occhio, bersaglio, max(2.0, dist * 0.02), geo.span * 70


class Segui:
    """La ripresa da dietro una macchina.

    La posizione resta attaccata alla macchina - a velocita' dieci una camera
    che la insegue con un ritardo resterebbe centinaia di metri indietro -
    mentre la direzione si gira con un po' di morbidezza, come un operatore
    che segue la curva invece di scattare.
    """

    def __init__(self):
        self.dir = None
        self.chi = None
        self.zoom = 1.0

    def rotella(self, y: float) -> None:
        self.zoom = max(0.5, min(4.0, self.zoom * (0.88 ** y)))

    def inquadra(self, geo, pos, fwd, chi, dt: float) -> tuple:
        fh = _norm((fwd[0], 0.0, fwd[2]))
        if self.dir is None or chi != self.chi:
            self.dir = fh
            self.chi = chi
        else:
            k = 1.0 - math.exp(-dt * 4.0)
            self.dir = _norm((self.dir[0] + (fh[0] - self.dir[0]) * k, 0.0,
                              self.dir[2] + (fh[2] - self.dir[2]) * k))
        d = self.dir
        dietro, su = 17.0 * self.zoom, 6.0 * self.zoom
        occhio = [pos[0] - d[0] * dietro, pos[1] + su, pos[2] - d[2] * dietro]
        occhio[1] = max(occhio[1], geo.terra(occhio[0], occhio[2]) + 2.0)
        bersaglio = (pos[0] + d[0] * 24.0, pos[1] + 1.5, pos[2] + d[2] * 24.0)
        return tuple(occhio), bersaglio, 0.5, geo.span * 70


_GEO: dict = {}


def geometria(track) -> pista3d.Geometria:
    """La geometria di un circuito, costruita una volta sola per partita."""
    g = _GEO.get(track.id)
    if g is None:
        _GEO.clear()
        g = _GEO[track.id] = pista3d.Geometria(track)
    return g


class Vista3D:
    """Una pista caricata sulla scheda video, pronta da disegnare."""

    def __init__(self, track):
        if not disponibile():
            raise RuntimeError("OpenGL non disponibile")
        ctx = self.ctx = _CTX
        self.geo = geometria(track)
        self.p_mondo = ctx.program(vertex_shader=_VS_MONDO, fragment_shader=_FS_MONDO)
        self.p_cielo = ctx.program(vertex_shader=_VS_CIELO, fragment_shader=_FS_CIELO)
        self.p_auto = ctx.program(vertex_shader=_VS_AUTO, fragment_shader=_FS_AUTO)
        self.vbo = ctx.buffer(self.geo.vert.tobytes())
        self.vao = ctx.vertex_array(self.p_mondo, [
            (self.vbo, "3f 3f 3f 1f", "in_pos", "in_nor", "in_col", "in_glow")])
        self.vbo_cielo = ctx.buffer(array("f", [-1, -1, 3, -1, -1, 3]).tobytes())
        self.vao_cielo = ctx.vertex_array(self.p_cielo, [(self.vbo_cielo, "2f", "in_ndc")])
        self.vbo_quad = ctx.buffer(array("f", [-0.5, -0.5, 0.5, -0.5, -0.5, 0.5, 0.5, 0.5]).tobytes())
        self.vbo_auto = ctx.buffer(reserve=64 * 10 * 4, dynamic=True)
        self.vao_auto = ctx.vertex_array(self.p_auto, [
            (self.vbo_quad, "2f", "in_corner"),
            (self.vbo_auto, "3f 3f 3f 1f/i", "i_pos", "i_fwd", "i_col", "i_sel")])
        img = _sagoma()
        self.tex = ctx.texture(img.get_size(), 4, pygame.image.tobytes(img, "RGBA"))
        self.tex.build_mipmaps()
        self.tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.elicottero = Elicottero()
        self.segui = Segui()
        self.fbo = self.fbo_ms = None
        self.misura = None
        self.mvp = None
        self.nuvole = 0.0

    def rilascia(self) -> None:
        for o in (self.vao, self.vbo, self.vao_cielo, self.vbo_cielo, self.vao_auto,
                  self.vbo_auto, self.vbo_quad, self.tex, self.p_mondo, self.p_cielo,
                  self.p_auto, self.fbo, self.fbo_ms):
            if o is not None:
                o.release()

    # --------------------------------------------------------------- luce
    def _luce(self) -> dict:
        notte = self.geo.notte
        n = max(0.0, min(1.0, self.nuvole))
        if notte:
            return dict(sun=_norm((-0.3, 0.8, -0.4)), sun_col=(0.07, 0.08, 0.12),
                        amb_sky=(0.07, 0.08, 0.12), amb_ground=(0.03, 0.03, 0.04),
                        zenit=(0.008, 0.012, 0.035), orizzonte=(0.05, 0.06, 0.11),
                        fari=1.0)
        sole = 1.0 - 0.7 * n
        mix = lambda a, b: tuple(x + (y - x) * n for x, y in zip(a, b))  # noqa: E731
        return dict(sun=_norm((-0.45, 0.62, -0.30)),
                    sun_col=(1.05 * sole, 0.98 * sole, 0.86 * sole),
                    amb_sky=mix((0.40, 0.46, 0.56), (0.58, 0.60, 0.64)),
                    amb_ground=mix((0.26, 0.24, 0.20), (0.32, 0.32, 0.33)),
                    zenit=mix((0.24, 0.45, 0.76), (0.44, 0.47, 0.52)),
                    orizzonte=mix((0.72, 0.80, 0.88), (0.64, 0.66, 0.70)),
                    fari=0.0)

    # ------------------------------------------------------------- disegno
    def _buffer(self, misura) -> None:
        if self.misura == misura:
            return
        for o in (self.fbo, self.fbo_ms):
            if o is not None:
                o.release()
        ctx = self.ctx
        campioni = min(4, ctx.max_samples)
        self.fbo_ms = ctx.framebuffer(
            ctx.renderbuffer(misura, 4, samples=campioni),
            ctx.depth_renderbuffer(misura, samples=campioni))
        self.fbo = ctx.framebuffer(ctx.renderbuffer(misura, 3))
        self.misura = misura

    def aggiorna(self, dt: float) -> None:
        self.elicottero.aggiorna(dt)

    def disegna(self, misura, auto: list, modo: str = "elicottero",
                seguita: int = -1, dt: float = 1 / 60) -> pygame.Surface:
        """Un fotogramma, grande `misura`.

        `auto` e' una lista di (frazione del giro, scostamento laterale in
        metri, colore 0..255, evidenziata). `seguita` e' l'indice in quella
        lista della macchina da seguire, se la ripresa e' da dietro.
        """
        misura = (max(16, int(misura[0])), max(16, int(misura[1])))
        self._buffer(misura)
        geo, ctx = self.geo, self.ctx
        posti = [geo.sul_giro(f, lat) for f, lat, _c, _s in auto]
        if modo == "segui" and 0 <= seguita < len(posti):
            pos, fwd = posti[seguita]
            occhio, bersaglio, vicino, lontano = self.segui.inquadra(geo, pos, fwd, seguita, dt)
            k_scala = 90.0
        else:
            occhio, bersaglio, vicino, lontano = self.elicottero.inquadra(
                geo, misura[0] / misura[1])
            k_scala = 420.0
        proj = _prospettiva(42.0 if modo == "segui" else 38.0,
                            misura[0] / misura[1], vicino, lontano)
        # la y si ribalta qui: OpenGL scrive le righe dal fondo, pygame le
        # legge dall'alto, e cosi' l'immagine esce gia' dritta
        mvp = _per(proj, _guarda(occhio, bersaglio))
        for c in range(4):
            mvp[c * 4 + 1] = -mvp[c * 4 + 1]
        self.mvp, self.occhio = mvp, occhio
        luce = self._luce()
        fog = luce["orizzonte"]
        fog_d = geo.span * 3.0

        self.fbo_ms.use()
        ctx.viewport = (0, 0, misura[0], misura[1])
        ctx.clear(*fog, 1.0)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE | moderngl.BLEND)
        pc = self.p_cielo
        pc["inv_vp"].write(array("f", _inversa(mvp)).tobytes())
        pc["eye"].value = occhio
        for k in ("zenit", "orizzonte", "sun", "sun_col"):
            pc[k].value = luce[k]
        self.vao_cielo.render(moderngl.TRIANGLES)

        ctx.enable(moderngl.DEPTH_TEST)
        pm = self.p_mondo
        pm["mvp"].write(array("f", mvp).tobytes())
        pm["eye"].value = occhio
        for k in ("sun", "sun_col", "amb_sky", "amb_ground", "fari"):
            pm[k].value = luce[k]
        pm["fog_col"].value = fog
        pm["fog_d"].value = fog_d
        self.vao.render(moderngl.TRIANGLES)

        if posti:
            dati = array("f")
            for (pos, fwd), (_f, _l, col, sel) in zip(posti, auto):
                dati.extend((pos[0], pos[1], pos[2], fwd[0], fwd[1], fwd[2],
                             col[0] / 255.0, col[1] / 255.0, col[2] / 255.0,
                             1.0 if sel else 0.0))
            self.vbo_auto.orphan(max(len(dati) * 4, 64 * 10 * 4))
            self.vbo_auto.write(dati.tobytes())
            pa = self.p_auto
            pa["mvp"].write(array("f", mvp).tobytes())
            pa["eye"].value = occhio
            pa["k_scala"].value = k_scala
            pa["sun"].value = luce["sun"]
            pa["sun_col"].value = luce["sun_col"]
            pa["amb_sky"].value = luce["amb_sky"]
            pa["fari"].value = luce["fari"]
            pa["fog_col"].value = fog
            pa["fog_d"].value = fog_d
            self.tex.use(0)
            pa["tex"].value = 0
            # prima le ombre, trasparenti e senza scrivere la profondita'
            ctx.enable(moderngl.BLEND)
            ctx.depth_mask = False
            pa["ombra"].value = 1.0
            self.vao_auto.render(moderngl.TRIANGLE_STRIP, instances=len(posti))
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
            pa["ombra"].value = 0.0
            self.vao_auto.render(moderngl.TRIANGLE_STRIP, instances=len(posti))

        ctx.copy_framebuffer(self.fbo, self.fbo_ms)
        dati = self.fbo.read(components=3, alignment=1)
        return pygame.image.frombytes(dati, misura, "RGB")

    def proietta(self, frazione: float, laterale: float = 0.0, alto: float = 0.0):
        """Dove cade sullo schermo un punto della pista, nell'ultimo fotogramma."""
        if self.mvp is None:
            return None
        (x, y, z), _ = self.geo.sul_giro(frazione, laterale)
        y += alto
        m = self.mvp
        cx = m[0] * x + m[4] * y + m[8] * z + m[12]
        cy = m[1] * x + m[5] * y + m[9] * z + m[13]
        cw = m[3] * x + m[7] * y + m[11] * z + m[15]
        if cw <= 0.1:
            return None
        return ((cx / cw * 0.5 + 0.5) * self.misura[0], (cy / cw * 0.5 + 0.5) * self.misura[1])
