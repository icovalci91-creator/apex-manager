from game.core import facilities as F

print("QUANTO PERDE UNA STRUTTURA DI LIVELLO 90, ANNO PER ANNO")
print("   anni dall'intervento   perdita   livello")
lvl = 90.0
for anno in range(0, 13):
    perdita = F.decay_of(lvl, anno)
    print("   %2d %-20s %.2f     %.1f" % (anno, "", perdita, lvl))
    lvl = max(F.FLOOR, lvl - perdita)

print()
print("CONFRONTO COL MODELLO PRECEDENTE (1.10 fisso, nessuna grazia)")
vecchio = 90.0
for anno in range(1, 11):
    vecchio -= 1.10 * (0.55 + 0.65 * vecchio / 100.0)
print("   dopo 10 anni senza investire:  prima %.1f  ->  ora %.1f" % (vecchio, lvl))

print()
print("COSTO PER STARE FERMI A 90 (galleria del vento, base 4.2)")
import game.config as C
prezzo = F.cost(90.0, C.FACILITIES["windtunnel"]["cost"])
guadagno = F.gain(90.0)
print("   un potenziamento: %.1f M$ per +%.1f punti" % (prezzo, guadagno))
print("   prima: ~%.2f punti persi l'anno -> %.1f M$/anno solo per non scendere"
      % (1.10 * 1.135, 1.10 * 1.135 / guadagno * prezzo))
media5 = sum(F.decay_of(90.0, a) for a in range(5)) / 5
print("   ora:   ~%.2f punti l'anno nei primi cinque -> %.1f M$/anno"
      % (media5, media5 / guadagno * prezzo))
