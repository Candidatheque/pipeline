# D'où vient chaque fichier

Les fichiers de ce dossier portent le texte des tableaux que le Conseil
constitutionnel annexe à sa proclamation, au Journal officiel : les résultats
des deux tours, département par département, « arrêtés conformément aux
tableaux annexés ». La pipeline les lit ; elle ne télécharge rien et n'ouvre
pas de PDF.

`seeds/resultats.yaml` fait foi : chaque version `rectification` y déclare son
édition dans le registre des sources, les pages de chaque tableau, ce que porte
chaque colonne, et les cases lues à la main sur l'image.

## Les éditions

Les PDF viennent de Légifrance, téléchargés à la main : le site refuse les
requêtes automatiques. Ils pèsent de 13 à 29 Mo et ne sont pas dans le dépôt.
Rejouer la commande sur la même édition rend le même texte.

| Fichier | Édition | SHA1 du PDF | Commande |
| ------- | ------- | ----------- | -------- |
| `1981.txt` | JO n° 115 du 16 mai 1981 | `87f6a569eae416b8c1ee75099cb2abe815d668a0` | `python outils/tableau_pdf_en_texte.py JORF_19810516_115.pdf --pages 4-9 --sortie raw/resultats/jo/1981.txt` |
| `1988.txt` | JO n° 111 du 12 mai 1988 | `461a469f79508a3f98e24c403e1bce99deae7d37` | `python outils/tableau_pdf_en_texte.py JORF_19880512_111.pdf --pages 6-11 --sortie raw/resultats/jo/1988.txt` |
| `1995.txt` | JO n° 113 du 14 mai 1995 | `89e3883507da5e73609a04e86078d939d9433a4a` | `python outils/tableau_pdf_en_texte.py JORF_19950514_113.pdf --pages 8-15 --sortie raw/resultats/jo/1995.txt` |

Les pages de la commande sont celles des tableaux ; dans le texte extrait,
chaque page est séparée de la suivante par un saut de page, et ce sont ces
pages-là, numérotées à partir de 1, que le seed déclare.

L'édition de 1974 — JO du 25 mai 1974, page 5669 — n'est pas accessible : la
décision 74-32 PDR la cite, mais la page de Légifrance renvoie une erreur. La
proclamation reste alors la dernière version de 1974. Avant, de 1965 à 1969, les
proclamations n'annexent pas de tableau.

## Le texte n'est pas transcrit

Ce texte est celui de la couche que Légifrance a océrisée, et l'archive de la
DILA n'en a pas d'autre : sa notice du 14 mai 1995 couvre 52 pages sans un seul
article transcrit. Il porte donc les fautes de l'océrisation — chiffres collés,
coupés, confondus, surtout le 3 et le 5 en 1981 — que la lecture redresse sur
les contrôles que le tableau porte lui-même, et que le seed complète de cases
lues sur l'image quand ces contrôles ne suffisent pas.
