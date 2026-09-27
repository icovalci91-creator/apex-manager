"""La pista in 3D disegnata da Panda3D.

Stessa scena e stessa interfaccia della vista in moderngl (`vista3d.Vista3D`,
da cui eredita tutto quello che non tocca la scheda video: la luce, il cielo
da scegliere, l'inquadratura, dove cade un punto sullo schermo), ma costruita
come la costruisce un motore: un grafo di nodi, ognuno con il suo shader e i
suoi parametri, disegnato da Panda3D in una catena di buffer fuori schermo.

Gli shader sono gli stessi: il pittore del mondo, le monoposto, il cielo, il
tavolo del plastico, le due sfocature e la passata finale. Cambia chi li
chiama. La catena, dal primo all'ultimo buffer:

  * le ombre: la profondita' del mondo vista dal sole, una volta sola;
  * la scena, con l'antialiasing e i colori oltre l'1: cielo (o tavolo),
    mondo, pareti del plastico, ombre sotto alle macchine, macchine;
  * due sfocature a mezza risoluzione, in orizzontale e in verticale;
  * la passata finale, alla misura piena, che si legge in memoria e diventa
    la Surface di pygame da incollare nella mappa.

Le macchine sono una monoposto sola disegnata ventidue volte (le istanze), con
posizione, direzione e colori di ognuna in un array che si riscrive a ogni
fotogramma.
"""
from __future__ import annotations

from array import array

import pygame

from . import monoposto, motore_panda as MP, qualita, risorse3d, vista3d
from .vista3d import (CARTA, ISTANZA, ISTANZE_MAX, _FS_AUTO, _FS_CIELO, _FS_FINALE,
                      _FS_MONDO, _FS_OMBRA, _FS_OMBRA_AUTO, _FS_PARETI, _FS_SFOCA,
                      _FS_TAVOLO, _VS_AUTO, _VS_MONDO, _VS_OMBRA, _VS_OMBRA_AUTO,
                      _VS_PARETI, _VS_PIENO, _inversa)


def _P():
    import panda3d.core as P
    return P


# ------------------------------------------------------------- mattoni
def _formato(colonne, divisore: int = 0):
    """Un array di vertici con le colonne che gli shader si aspettano, per nome."""
    P = _P()
    a = P.GeomVertexArrayFormat()
    for nome, n in colonne:
        a.add_column(P.InternalName.make(nome), n, P.Geom.NT_float32, P.Geom.C_other)
    if divisore:
        a.set_divisor(divisore)
    return a


def _nodo(nome: str, formati: list, dati: list, vertici: int):
    """Un nodo con una geometria di triangoli. `dati`: per ogni array i byte,
    o un GeomVertexArrayData gia' fatto (condiviso fra piu' nodi). Il nodo non
    si scarta mai per inquadratura: le matrici le calcola il gioco."""
    P = _P()
    fmt = P.GeomVertexFormat()
    for a in formati:
        fmt.add_array(a)
    fmt = P.GeomVertexFormat.register_format(fmt)
    vd = P.GeomVertexData(nome, fmt, P.Geom.UH_static)
    for i, d in enumerate(dati):
        if isinstance(d, P.GeomVertexArrayData):
            vd.set_array(i, d)
            continue
        arr = vd.modify_array(i)
        arr.unclean_set_num_rows(len(d) // fmt.get_array(i).get_stride())
        arr.modify_handle().copy_data_from(d)
    tri = P.GeomTriangles(P.Geom.UH_static)
    tri.add_consecutive_vertices(0, vertici)
    g = P.Geom(vd)
    g.add_primitive(tri)
    gn = P.GeomNode(nome)
    gn.add_geom(g)
    gn.set_bounds(P.OmniBoundingVolume())
    gn.set_final(True)
    return P.NodePath(gn)


def _quad(nome: str):
    """Il triangolo che copre tutto lo schermo, per cielo, tavolo e passate."""
    fmt = _formato([("in_ndc", 2)])
    return _nodo(nome, [fmt], [array("f", [-1, -1, 3, -1, -1, 3]).tobytes()], 3)


def _shader(vs: str, fs: str):
    P = _P()
    return P.Shader.make(P.Shader.SL_GLSL, vs, fs)


def _camera(radice):
    """Una camera che guarda `radice`: la lente non conta, le matrici le
    passano gli shader."""
    P = _P()
    cam = P.Camera("camera")
    cam.set_lens(P.OrthographicLens())
    cam.set_scene(radice)
    cam.set_cull_bounds(P.OmniBoundingVolume())
    return P.NodePath(cam)


def _m4(flat):
    """Una matrice nostra (per colonne, come OpenGL) per uno shader di Panda3D:
    in memoria sono la stessa cosa."""
    return _P().LMatrix4f(*[float(v) for v in flat])


def _v(t):
    P = _P()
    t = tuple(float(x) for x in t)
    return {2: P.LVecBase2f, 3: P.LVecBase3f, 4: P.LVecBase4f}[len(t)](*t)


def _tela_array(dati: bytes, w: int, h: int, n: int, componenti: int, mip: bool = True,
                ripeti: bool = True):
    P = _P()
    t = P.Texture()
    t.setup_2d_texture_array(w, h, n, P.Texture.T_unsigned_byte,
                             P.Texture.F_rgb if componenti == 3 else P.Texture.F_red)
    if componenti == 3:
        t.set_ram_image_as(dati, "RGB")
    else:
        t.set_ram_image(dati)
    t.set_minfilter(P.SamplerState.FT_linear_mipmap_linear if mip else P.SamplerState.FT_linear)
    t.set_magfilter(P.SamplerState.FT_linear)
    modo = P.SamplerState.WM_repeat if ripeti else P.SamplerState.WM_clamp
    t.set_wrap_u(modo)
    t.set_wrap_v(modo)
    if mip:
        t.set_anisotropic_degree(8)
    return t


def _tela_virgola(img, ripeti_u: bool = True):
    """Una foto a colori oltre l'1 (numpy float32, altezza x larghezza x 3)."""
    P = _P()
    h, w = img.shape[:2]
    t = P.Texture()
    t.setup_2d_texture(w, h, P.Texture.T_float, P.Texture.F_rgb32)
    t.set_ram_image_as(img.tobytes(), "RGB")
    t.set_minfilter(P.SamplerState.FT_linear)
    t.set_magfilter(P.SamplerState.FT_linear)
    t.set_wrap_u(P.SamplerState.WM_repeat if ripeti_u else P.SamplerState.WM_clamp)
    t.set_wrap_v(P.SamplerState.WM_clamp)
    return t


def _tela_semplice(tex, lineare: bool = True):
    P = _P()
    f = P.SamplerState.FT_linear if lineare else P.SamplerState.FT_nearest
    tex.set_minfilter(f)
    tex.set_magfilter(f)
    tex.set_wrap_u(P.SamplerState.WM_clamp)
    tex.set_wrap_v(P.SamplerState.WM_clamp)
    return tex


# ------------------------------------------------------------------ vista
class VistaPanda(vista3d.Vista3D):
    """Una pista caricata in Panda3D, pronta da disegnare."""

    def __init__(self, track, tipo: str = "f1"):
        if not MP.disponibile():
            raise RuntimeError(f"Panda3D non disponibile: {MP.errore()}")
        P = _P()
        self.q = dict(qualita.attuale())
        self.versione_qualita = qualita.VERSIONE[0]
        self.geo = vista3d.geometria(track, self.q.get("dettaglio"))
        self.tipo = tipo
        self.ombra_misura = int(self.q["ombre"])
        # lo stato che la mappa legge e scrive, come in Vista3D
        self.plastico = False
        self.tavola = None
        self.auto = []
        self.scala_auto = 1.0
        self.spostamento = 0.0
        self.tex_livree = None
        self.elicottero = vista3d.Elicottero()
        self.camera = None
        self.replay = 0.0
        self.misura = None
        self.misura_logica = None
        self.mvp = None
        self.nuvole = 0.0
        self.bagnato = 0.0
        self.tempo = 0.0
        self.cieli = {}
        self.cielo = None
        self._cielo_nome = None
        self.uscite = {}
        self.interna = self.mezza = None

        # --- la scena: il cielo (o il tavolo), il mondo, le macchine
        self.scena = P.NodePath("scena")
        self.n_cielo = _quad("cielo")
        self.n_cielo.set_shader(_shader(_VS_PIENO, _FS_CIELO))
        self.n_tavolo = _quad("tavolo")
        self.n_tavolo.set_shader(_shader(_VS_PIENO, _FS_TAVOLO))
        for n in (self.n_cielo, self.n_tavolo):
            n.reparent_to(self.scena)
            n.set_bin("background", 0)
            n.set_depth_test(False)
            n.set_depth_write(False)
        self.n_tavolo.hide()
        fmt_mondo = _formato([("in_pos", 3), ("in_nor", 3), ("in_col", 3), ("in_glow", 1),
                              ("in_mat", 1), ("in_par", 1), ("in_aux", 1)])
        geom_mondo = _nodo("mondo", [fmt_mondo], [self.geo.vert.tobytes()],
                           len(self.geo.vert) // 13)
        # lo shader sta sul nodo sopra: la stessa geometria serve anche alle ombre
        self.n_mondo = self.scena.attach_new_node("mondo")
        self.n_mondo.set_shader(_shader(_VS_MONDO, _FS_MONDO))
        self.n_mondo.set_bin("fixed", 10)
        self.n_mondo.set_two_sided(True)
        geom_mondo.reparent_to(self.n_mondo)
        self.n_pareti = None

        # le monoposto: la forma una volta, le istanze a ogni fotogramma
        fine = bool(self.q.get("dettaglio"))
        forma = monoposto.mesh_fe(fine) if tipo == "fe" else monoposto.mesh(fine)
        fmt_auto = _formato([("in_pos", 3), ("in_nor", 3), ("in_parte", 1)])
        fmt_ist = _formato([("i_pos", 3), ("i_fwd", 3), ("i_col", 3), ("i_col2", 3),
                            ("i_stile", 1), ("i_gomma", 3), ("i_livrea", 1)], divisore=1)
        fmt_tutto = P.GeomVertexFormat()
        fmt_tutto.add_array(fmt_auto)
        fmt_tutto.add_array(fmt_ist)
        fmt_tutto = P.GeomVertexFormat.register_format(fmt_tutto)
        self.istanze = P.GeomVertexArrayData(fmt_tutto.get_array(1), P.Geom.UH_dynamic)
        self.istanze.unclean_set_num_rows(ISTANZE_MAX)
        self.n_auto = _nodo("auto", [fmt_auto, fmt_ist], [forma.tobytes(), self.istanze],
                            len(forma) // 7)
        self.n_auto.reparent_to(self.scena)
        self.n_auto.set_shader(_shader(_VS_AUTO, _FS_AUTO))
        self.n_auto.set_bin("fixed", 30)
        self.n_auto.set_two_sided(True)
        fmt_q = _formato([("in_q", 2)])
        self.n_macchie = _nodo("macchie", [fmt_q, fmt_ist],
                               [array("f", [-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1]).tobytes(),
                                self.istanze], 6)
        self.n_macchie.reparent_to(self.scena)
        self.n_macchie.set_shader(_shader(_VS_OMBRA_AUTO, _FS_OMBRA_AUTO))
        self.n_macchie.set_bin("fixed", 20)
        self.n_macchie.set_two_sided(True)
        self.n_macchie.set_depth_write(False)
        self.n_macchie.set_transparency(P.TransparencyAttrib.M_alpha)

        # --- le ombre: la stessa geometria del mondo, vista dal sole
        self.radice_ombre = P.NodePath("ombre")
        self.radice_ombre.set_shader(_shader(_VS_OMBRA, _FS_OMBRA))
        self.radice_ombre.set_two_sided(True)
        geom_mondo.instance_to(self.radice_ombre)
        self.b_ombre, self.tex_ombre = MP.buffer("ombre", (self.ombra_misura,) * 2, -10,
                                                 solo_profondita=True)
        if self.b_ombre is None:
            raise RuntimeError("Panda3D: niente buffer per le ombre")
        self.tex_ombre.set_minfilter(P.SamplerState.FT_shadow)
        self.tex_ombre.set_magfilter(P.SamplerState.FT_shadow)
        self.tex_ombre.set_wrap_u(P.SamplerState.WM_clamp)
        self.tex_ombre.set_wrap_v(P.SamplerState.WM_clamp)
        self.b_ombre.set_clear_depth_active(True)
        self.b_ombre.set_clear_depth(1.0)
        self.b_ombre.make_display_region().set_camera(_camera(self.radice_ombre))
        self.b_ombre.set_active(False)

        # --- le tele: materiali fotografici, e quelle vuote da tenere agganciate
        self.materiali = None
        if self.q["texture"]:
            try:
                d = risorse3d.dati_materiali(int(self.q["texture"]))
            except Exception:
                d = None
            if d is not None:
                lato, n = d["lato"], d["strati"]
                self.materiali = {
                    "colore": _tela_array(d["colore"], lato, lato, n, 3),
                    "normale": _tela_array(d["normale"], lato, lato, n, 3),
                    "ruvidita": _tela_array(d["ruvidita"], lato, lato, n, 1),
                    "medie": d["medie"], "presenti": d["presenti"], "metri": d["metri"]}
        self.tex_mat_vuota = _tela_array(b"\x80\x80\x80" * 6, 1, 1, 6, 3, mip=False)
        self.tex_rug_vuota = _tela_array(b"\xc8" * 6, 1, 1, 6, 1, mip=False)
        import numpy as np
        self.tex_cielo_vuoto = _tela_virgola(np.zeros((1, 1, 3), dtype=np.float32))
        self.tex_vuota = _tela_array(b"\xff\xff\xff", 1, 1, 1, 3, mip=False)
        self._ombre()

    # --------------------------------------------------------- risorse
    def _carica_cielo(self, nome: str):
        d = risorse3d.dati_cielo(nome, int(self.q["cielo"]))
        if d is None:
            return None
        fuori = dict(d)
        fuori["tex"] = _tela_virgola(fuori.pop("img"))
        return fuori

    def carica_livree(self, tele: list) -> None:
        """Le livree delle squadre, una tela per squadra (vedi `livree`)."""
        self.tex_livree = None
        if not tele:
            return
        w, h = tele[0].get_size()
        pezzi = []
        for t in tele:
            if t.get_size() != (w, h):
                t = pygame.transform.smoothscale(t, (w, h))
            pezzi.append(pygame.image.tobytes(t, "RGB"))
        self.tex_livree = _tela_array(b"".join(pezzi), w, h, len(tele), 3, ripeti=False)

    # ----------------------------------------------------------- ombre
    def _ombre(self) -> None:
        """Le ombre si calcolano una volta: il sole e la scena non si muovono."""
        self.luce_vp = self._vp_luce()
        self.radice_ombre.set_shader_input("luce_vp", _m4(self.luce_vp))
        self._solo(self.b_ombre)

    def _rifai_ombre(self) -> None:
        self._ombre()

    def _solo(self, buffer) -> None:
        """Disegna un fotogramma con acceso solo `buffer`, poi lo rispegne."""
        # un buffer appena nato non si dice ancora acceso: si spengono tutti
        catena = self._catena()
        for b in catena:
            b.set_active(False)
        buffer.set_active(True)
        MP.motore().render_frame()
        buffer.set_active(False)
        for b in catena:
            b.set_active(True)

    # ----------------------------------------------------------- plastico
    def _tavola(self) -> tuple:
        if self.tavola is not None:
            return self.tavola
        dati, self.tavola = self._dati_tavola()
        fmt = _formato([("in_pos", 3), ("in_col", 3), ("in_nor", 3)])
        self.n_pareti = _nodo("pareti", [fmt], [dati.tobytes()], len(dati) // 9)
        self.n_pareti.reparent_to(self.scena)
        self.n_pareti.set_shader(_shader(_VS_PARETI, _FS_PARETI))
        self.n_pareti.set_bin("fixed", 11)
        self.n_pareti.set_two_sided(True)
        self.n_pareti.hide()
        return self.tavola

    # ----------------------------------------------------------- buffer
    def _catena(self) -> list:
        return [b for b in (self.uscite.get(k) for k in ("scena", "a", "b", "fine"))
                if b is not None]

    def _buffer(self, misura) -> None:
        if self.misura == misura:
            return
        for b in self._catena():
            MP.togli(b)
        self.uscite = {}
        # la scena si disegna alla risoluzione che la qualita' concede; la
        # passata finale torna alla misura piena
        k = float(self.q["scala3d"])
        interna = (max(16, int(misura[0] * k)), max(16, int(misura[1] * k)))
        mezza = (max(8, interna[0] // 2), max(8, interna[1] // 2))
        campioni = int(self.q["msaa"])
        b, t = (None, None)
        while b is None:
            b, t = MP.buffer("scena", interna, 0, campioni=campioni if campioni >= 2 else 0)
            if b is None:
                if campioni < 2:
                    raise RuntimeError("Panda3D: niente buffer per la scena")
                campioni //= 2
        _tela_semplice(t)
        b.set_clear_color_active(True)
        b.set_clear_depth_active(True)
        b.set_clear_depth(1.0)
        b.make_display_region().set_camera(_camera(self.scena))
        self.uscite["scena"], self.t_scena = b, t
        # le due sfocature
        self.quad_a, self.quad_b = _quad("sfoca_a"), _quad("sfoca_b")
        sorgente = t
        for chiave, quad, ordine, passo in (("a", self.quad_a, 10, (2.0 / interna[0], 0.0)),
                                            ("b", self.quad_b, 20, (0.0, 2.0 / interna[1]))):
            bb, tt = MP.buffer("sfoca_" + chiave, mezza, ordine, profondita=False)
            if bb is None:
                raise RuntimeError("Panda3D: niente buffer per la sfocatura")
            _tela_semplice(tt)
            quad.set_shader(_shader(_VS_PIENO, _FS_SFOCA))
            quad.set_shader_inputs(tex=sorgente, passo=_v(passo))
            quad.set_depth_test(False)
            quad.set_depth_write(False)
            bb.make_display_region().set_camera(_camera(quad))
            self.uscite[chiave] = bb
            setattr(self, "t_" + chiave, tt)
            sorgente = tt
        # la passata finale, che si legge
        bf, tf = MP.buffer("fine", misura, 30, virgola=False, profondita=False, ram=True)
        if bf is None:
            raise RuntimeError("Panda3D: niente buffer per il fotogramma")
        self.quad_fine = _quad("finale")
        self.quad_fine.set_shader(_shader(_VS_PIENO, _FS_FINALE))
        self.quad_fine.set_shader_inputs(scena=self.t_scena, sfocata=self.t_b)
        self.quad_fine.set_depth_test(False)
        self.quad_fine.set_depth_write(False)
        bf.make_display_region().set_camera(_camera(self.quad_fine))
        self.uscite["fine"], self.t_fine = bf, tf
        self.interna, self.mezza, self.misura = interna, mezza, misura

    # ----------------------------------------------------------- disegno
    def disegna(self, misura) -> pygame.Surface:
        """Un fotogramma della pista, grande `misura`, con le macchine di `self.auto`."""
        P = _P()
        misura = (max(16, int(misura[0])), max(16, int(misura[1])))
        self._buffer(misura)
        geo = self.geo
        occhio, mvp, fog_d, fuoco, regia, plastico = self._inquadra(misura)
        self._scegli_cielo()
        luce = self._luce()
        cielo_tex = self.cielo["tex"] if self.cielo else self.tex_cielo_vuoto
        con_cielo = 1.0 if self.cielo is not None else 0.0
        scena = self.uscite["scena"]
        m_mvp, m_inv = _m4(mvp), _m4(_inversa(mvp))
        if plastico:
            tav = self._tavola()
            scena.set_clear_color(_v(CARTA + (1.0,)))
            self.n_cielo.hide()
            self.n_tavolo.show()
            sole = luce["sun"]
            salto = tav[4] - tav[5]
            self.n_tavolo.set_shader_inputs(
                inv_vp=m_inv, eye=_v(occhio), taglio=_v(tav[:4]), quota=float(tav[5]),
                ombra_dx=_v((-sole[0] / max(0.2, sole[1]) * salto,
                             -sole[2] / max(0.2, sole[1]) * salto)),
                passo=float(max(20.0, round(geo.span / 30.0, -1))), carta=_v(CARTA))
            fog_d = geo.span * 14.0
        else:
            scena.set_clear_color(_v(tuple(luce["orizzonte"]) + (1.0,)))
            self.n_tavolo.hide()
            self.n_cielo.show()
            self.n_cielo.set_shader_inputs(
                inv_vp=m_inv, eye=_v(occhio), zenit=_v(luce["zenit"]),
                orizzonte=_v(luce["orizzonte"]), sun=_v(luce["sun"]),
                sun_col=_v(luce["sun_col"]), stelle=float(luce["stelle"]),
                cielo_tex=cielo_tex, con_cielo=con_cielo)
        if self.n_pareti is not None:
            if plastico:
                self.n_pareti.show()
                self.n_pareti.set_shader_inputs(mvp=m_mvp, sun=_v(luce["sun"]),
                                                sun_col=_v(luce["sun_col"]),
                                                amb_sky=_v(luce["amb_sky"]))
            else:
                self.n_pareti.hide()

        # il mondo
        mat = self.materiali
        comuni = dict(sun=_v(luce["sun"]), sun_col=_v(luce["sun_col"]),
                      amb_sky=_v(luce["amb_sky"]), amb_ground=_v(luce["amb_ground"]),
                      fari=float(luce["fari"]), zenit=_v(luce["zenit"]),
                      fog_col=_v(CARTA if plastico else luce["orizzonte"]),
                      fog_d=float(fog_d), eye=_v(occhio), mvp=m_mvp,
                      luce_vp=_m4(self.luce_vp), texel=1.0 / self.ombra_misura,
                      ombre=self.tex_ombre, cielo_tex=cielo_tex, con_cielo=con_cielo,
                      bagnato=max(0.0, min(1.0, float(self.bagnato))))
        medie = P.PTA_LVecBase3f()
        metri, presenti = P.PTA_float(), P.PTA_float()
        for i in range(6):
            if mat is not None:
                medie.push_back(P.LVecBase3f(*mat["medie"][i]))
                metri.push_back(float(mat["metri"][i]))
                presenti.push_back(1.0 if mat["presenti"][i] else 0.0)
            else:
                medie.push_back(P.LVecBase3f(0.5, 0.5, 0.5))
                metri.push_back(3.0)
                presenti.push_back(0.0)
        taglio = self.tavola[:4] if plastico else (-1e9, 1e9, -1e9, 1e9)
        self.n_mondo.set_shader_inputs(
            tempo=float(self.tempo), nuvole=max(0.0, min(1.0, float(self.nuvole))),
            origine=_v((geo.cx, geo.cz)), blocco=float(vista3d.pista3d.BLOCCO),
            stile=P.PTA_int([{"parco": 0, "bosco": 1, "dune": 2}.get(geo.bioma, 0)]),
            riva=1.0 if geo.acqua else 0.0,
            mat_col=mat["colore"] if mat else self.tex_mat_vuota,
            mat_nor=mat["normale"] if mat else self.tex_mat_vuota,
            mat_rug=mat["ruvidita"] if mat else self.tex_rug_vuota,
            mat_media=medie, mat_metri=metri, mat_c=presenti,
            con_foto=1.0 if mat is not None else 0.0,
            plastico=1.0 if plastico else 0.0, taglio=_v(taglio), **comuni)

        # le macchine
        dati = self._dati_istanze() if self.auto else array("f")
        quante = len(dati) // ISTANZA
        if quante:
            h = self.istanze.modify_handle()
            pieno = dati + array("f", [0.0]) * (ISTANZE_MAX * ISTANZA - len(dati))
            h.copy_data_from(pieno.tobytes())
            for n in (self.n_auto, self.n_macchie):
                n.show()
                n.set_instance_count(quante)
            sole = luce["sun"]
            k = 0.9 / max(0.25, sole[1])
            self.n_macchie.set_shader_inputs(
                mvp=m_mvp, sole_xz=_v((-sole[0] * k, 0.0, -sole[2] * k)),
                forza=0.35 if geo.notte else 0.55, scala=float(self.scala_auto))
            auto = dict(comuni)
            # le macchine si sfumano verso l'orizzonte anche sul plastico
            auto["fog_col"] = _v(luce["orizzonte"])
            self.n_auto.set_shader_inputs(
                scala=float(self.scala_auto),
                livree=self.tex_livree if self.tex_livree is not None else self.tex_vuota,
                **auto)
        else:
            self.n_auto.hide()
            self.n_macchie.hide()

        # la passata finale
        vicino = self.elicottero.chi is not None and self.elicottero.zoom_auto < 0.5
        tilt = 0.0 if regia else 0.85 * (
            min(1.0, self.elicottero.zoom_auto / 0.5) if vicino else 1.0)
        self.quad_fine.set_shader_inputs(
            notte=1.0 if geo.notte else 0.0, tilt=float(tilt), fuoco=_v(fuoco),
            replay=max(0.0, min(1.0, float(self.replay))))
        MP.motore().render_frame()
        dati_img = self.t_fine.get_ram_image_as("RGB")
        # le righe arrivano dal fondo, e l'immagine e' gia' ribaltata nella
        # matrice della vista: si legge cosi' com'e'
        return pygame.image.frombuffer(bytes(dati_img), misura, "RGB")

    # --------------------------------------------------------- chiusura
    def rilascia(self) -> None:
        for b in self._catena():
            MP.togli(b)
        MP.togli(self.b_ombre)
        self.uscite = {}
        self.b_ombre = None
        self.scena.remove_node()
        self.radice_ombre.remove_node()
        self.cieli = {}
        self.materiali = None
        self.tex_livree = None
