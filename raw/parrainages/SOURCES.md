# D'où vient chaque fichier

Les fichiers de ce dossier sont les sources des parrainages, telles qu'elles
ont été publiées. La pipeline les lit ; elle ne télécharge rien.

`seeds/parrainages.yaml` fait foi : chaque entrée y déclare son `origine`, qui
renvoie au registre des sources, et ses paramètres de conversion. Ce fichier-ci
ne donne que la marche à suivre pour reconstituer le texte.

## Les JSON de 2017 et 2022

Ils viennent tels quels de l'open data du Conseil constitutionnel, déposé sur
data.gouv.fr, et sont repris sans retouche. Leur empreinte est celle de la
ressource publiée :

| Fichier     | SHA1                                       |
| ----------- | ------------------------------------------ |
| `2017.json` | `ff9fd796b590c57a0edcd2c4ef1c6faa776714cf` |
| `2022.json` | `b6d4f770c5adc1dd2b69a23271cb6dd878af2d1c` |

## Les textes antérieurs

Ils sont extraits des éditions du Journal officiel. Les PDF de 1981, 1988 et
1995 mis en ligne par Légifrance pèsent de 16 à 51 Mo et ne sont pas dans le
dépôt ; ceux de 2007 et 2012, publiés par le Conseil constitutionnel, y sont.
Rejouer la commande sur le même PDF rend le même texte.

| Fichier    | Édition du Journal officiel | Commande                                                                                           |
| ---------- | --------------------------- | -------------------------------------------------------------------------------------------------- |
| `1981.txt` | n° 90 du 15 avril 1981      | `python outils/pdf_en_texte.py JORF_19810415_90.pdf --pages 2-25 --sortie raw/parrainages/1981.txt` |
| `1988.txt` | n° 86 du 12 avril 1988      | `python outils/pdf_en_texte.py JORF_19880412_86.pdf --pages 7-27 --sortie raw/parrainages/1988.txt` |
| `1995.txt` | n° 87 du 12 avril 1995      | `python outils/pdf_en_texte.py JORF_19950412_87.pdf --pages 8-30 --sortie raw/parrainages/1995.txt` |
| `2002.txt` | n° 84 du 10 avril 2002      | voir ci-dessous, texte transcrit par la DILA                                                        |
| `2007.txt` | n° 71 du 24 mars 2007       | `python outils/pdf_en_texte.py raw/parrainages/2007.pdf`                                            |
| `2012.txt` | n° 78 du 31 mars 2012       | `python outils/pdf_en_texte.py raw/parrainages/2012.pdf`                                            |

Les pages indiquées dans la commande sont celles des listes elles-mêmes : le
reste de l'édition porte d'autres textes, qui n'ont rien à y faire. Elles
figurent aussi dans le seed, sous `pages`.

## 2002, transcrit plutôt qu'océrisé

Les éditions anciennes existent aussi en texte transcrit dans les données
ouvertes de la DILA, et quand la transcription existe elle vaut mieux : elle ne
porte aucune des blessures de l'impression. C'est le cas de 2002.

L'archive `Freemium_jorf_global` est un tar gzippé de 1,6 Go, sans index : on
ne saute pas au fichier voulu, mais son chemin se déduit de l'identifiant — les
dix premiers chiffres, par paires — ce qui évite d'ouvrir les autres. La
télécharger une fois sur disque plutôt que la relire en flux : le serveur coupe
la connexion sans prévenir, et `tar` sort alors sans rien signaler.

    curl -O https://echanges.dila.gouv.fr/OPENDATA/JORF/Freemium_jorf_global_<horodatage>.tar.gz
    tar -xzf Freemium_jorf_global_<horodatage>.tar.gz \
        jorf/global/texte/struct/JORF/TEXT/00/00/00/40/75/JORFTEXT000000407519.xml
    tar -xzf Freemium_jorf_global_<horodatage>.tar.gz \
        jorf/global/article/JORF/ARTI/00/00/01/82/26/JORFARTI000001822602.xml
    python outils/jorf_xml_en_texte.py JORFARTI000001822602.xml \
        --sortie raw/parrainages/2002.txt

Le fichier de structure donne les articles du texte ; ici un seul, qui porte
les seize listes.
