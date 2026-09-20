# D'où vient chaque fichier

Les fichiers de ce dossier sont les sources des parrainages, telles qu'elles
ont été publiées. La pipeline les lit ; elle ne télécharge rien.

Les JSON de 2017 et 2022 viennent tels quels de l'open data du Conseil
constitutionnel. Les textes antérieurs sont extraits des éditions du Journal
officiel mises en ligne par Légifrance : ces PDF pèsent de 16 à 51 Mo et ne
sont pas dans le dépôt, mais la commande qui en tire le texte est donnée
ci-dessous, et la rejouer sur le même PDF rend le même fichier.

| Fichier    | Édition du Journal officiel | Pages | Commande                                                                     |
| ---------- | --------------------------- | ----- | ---------------------------------------------------------------------------- |
| `1981.txt` | JORF n° 90 du 15 avril 1981 | 2-25  | `python outils/pdf_en_texte.py JORF_19810415_90.pdf --pages 2-25 --sortie raw/parrainages/1981.txt` |
| `1988.txt` | JORF n° 86 du 12 avril 1988 | 7-27  | `python outils/pdf_en_texte.py JORF_19880412_86.pdf --pages 7-27 --sortie raw/parrainages/1988.txt` |
| `1995.txt` | JORF n° 87 du 12 avril 1995 | 8-30  | `python outils/pdf_en_texte.py JORF_19950412_87.pdf --pages 8-30 --sortie raw/parrainages/1995.txt` |
| `2007.txt` | JORF n° 68 du 21 mars 2007  | tout  | `python outils/pdf_en_texte.py 2007.pdf --sortie raw/parrainages/2007.txt`    |
| `2012.txt` | JORF n° 73 du 25 mars 2012  | tout  | `python outils/pdf_en_texte.py 2012.pdf --sortie raw/parrainages/2012.txt`    |

Les pages indiquées sont celles des listes elles-mêmes : le reste de l'édition
porte d'autres textes, qui n'ont rien à y faire.
