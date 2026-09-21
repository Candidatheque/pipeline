# D'où vient chaque fichier

Les fichiers de ce dossier portent le texte des décisions par lesquelles le
Conseil constitutionnel déclare les résultats du premier tour, puis proclame
ceux de l'élection. La pipeline les lit ; elle ne télécharge rien.

`seeds/resultats.yaml` fait foi : chaque entrée y déclare son `origine`, qui
renvoie au registre des sources. Ce fichier-ci ne donne que la marche à suivre
pour reconstituer le texte.

Chacun se rejoue avec la même commande, sur la page dont l'URL est donnée :

    python outils/decision_cc_en_texte.py <url> --sortie raw/resultats/<fichier>

Le texte produit porte deux sections. `DÉCISION` est le document lui-même : les
considérants qui annulent des suffrages, puis celui qui donne les résultats du
tour. `ABSTRACTS` est le classement que le Conseil fait de ses propres motifs
— « 8.2.5.4.1. Procédure de dépouillement » —, avec le numéro du considérant
que chacun résume. Les décisions anciennes n'en ont pas, et la section est
alors vide.

| Fichier | Décision | Page |
| ------- | -------- | ---- |
| `65-6-PDR.txt` | Déclaration du 7 décembre 1965 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1965/656pdr.htm` |
| `65-10-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1965/6510pdr.htm` |
| `69-20-PDR.txt` | Déclaration du 3 juin 1969 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1969/6920PDR.htm` |
| `69-22-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1969/6922pdr.htm` |
| `74-30-PDR.txt` | Déclaration du 7 mai 1974 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1974/7430pdr.htm` |
| `74-32-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1974/7432PDR.htm` |
| `81-45-PDR.txt` | Déclaration du 29 avril 1981 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1981/8145pdr.htm` |
| `81-47-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1981/8147pdr.htm` |
| `88-56-PDR.txt` | Déclaration du 27 avril 1988 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1988/8856pdr.htm` |
| `88-60-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1988/8860PDR.htm` |
| `95-79-PDR.txt` | Déclaration du 26 avril 1995 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/1995/9579pdr.htm` |
| `95-81-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/1995/9581PDR.htm` |
| `2002-109-PDR.txt` | Déclaration du 24 avril 2002 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/2002/2002109PDR.htm` |
| `2002-111-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/2002/2002111PDR.htm` |
| `2007-139-PDR.txt` | Déclaration du 25 avril 2007 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/2007/2007139PDR.htm` |
| `2007-141-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/2007/2007141pdr.htm` |
| `2012-152-PDR.txt` | Déclaration du 25 avril 2012 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/2012/2012152PDR.htm` |
| `2012-154-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/2012/2012154PDR.htm` |
| `2017-169-PDR.txt` | Déclaration du 26 avril 2017 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/2017/2017169PDR.htm` |
| `2017-171-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/2017/2017171PDR.htm` |
| `2022-195-PDR.txt` | Déclaration du 13 avril 2022 relative aux résultats du premier tour | `https://www.conseil-constitutionnel.fr/decision/2022/2022195PDR.htm` |
| `2022-197-PDR.txt` | Proclamation des résultats de l'élection | `https://www.conseil-constitutionnel.fr/decision/2022/2022197PDR.htm` |

Deux décisions de 1974 portent la même date : la 74-32 proclame les résultats,
la 74-33 est le texte d'observations du Conseil sur le déroulement du scrutin.
Seule la première est ici.

Le texte des décisions anciennes est une transcription, et elle porte les
blessures de l'impression d'époque : « 36 398762 » pour un nombre coupé,
« le l bureau » pour « le 1er bureau », « l 260 208 » pour « 1 260 208 ». La
lecture les redresse ; c'est son travail, et elle refuse ce qu'elle ne sait pas
lire plutôt que de le deviner.
