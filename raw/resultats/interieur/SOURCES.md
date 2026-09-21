# D'où vient chaque fichier

Les fichiers de ce dossier portent les résultats du ministère de l'Intérieur,
tels qu'il les publie sur data.gouv.fr, recopiés en CSV. La pipeline les lit ;
elle ne télécharge rien, et n'ouvre ni classeur Excel ni fichier Latin-1.

`seeds/resultats.yaml` fait foi : chaque version y déclare son `origine`, le
jeu de données dans le registre des sources, et ses deux fichiers. Ce fichier-ci
donne la ressource exacte et la marche à suivre pour reconstituer le CSV.

Deux formats d'origine :

- **2022** : un texte séparé par des points-virgules, en Latin-1, un fichier
  pour la France entière et un par département ;
- **2007 à 2017** : un classeur Excel par tour — par élection en 2007 et 2012 —
  dont on ne tire que deux feuilles, la fiche « France entière » et le tableau
  des départements. Les autres feuilles, régions, circonscriptions et cantons,
  ne sont pas reprises.

`outils/interieur_en_csv.py` recopie chaque cellule telle quelle. Seuls
changent les artefacts du format : un entier qu'Excel stocke en flottant, et
l'espace insécable des milliers. Il demande `xlrd`, dans les dépendances
`outils` du paquet.

Les empreintes sont celles des fichiers téléchargés, avant conversion. Dans
les commandes, le fichier téléchargé est renommé d'après le CSV qu'il produit :
les ressources de 2022 portent le même nom pour les résultats provisoires et
définitifs, et seul leur répertoire les distingue.

| Fichier | Ressource publiée | SHA1 | Commande |
| ------- | ----------------- | ---- | -------- |
| `2007-t1-definitifs-departements.csv` | [b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d4380](https://static.data.gouv.fr/fb/b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d43805a734479294899.xls) | `dfa0fccf37e3c4898427e211e757054c889d9915` | `python outils/interieur_en_csv.py 2007-definitifs.xls --feuille "Départements T1" --sortie raw/resultats/interieur/2007-t1-definitifs-departements.csv` |
| `2007-t1t2-definitifs-france.csv` | [b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d4380](https://static.data.gouv.fr/fb/b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d43805a734479294899.xls) | `dfa0fccf37e3c4898427e211e757054c889d9915` | `python outils/interieur_en_csv.py 2007-definitifs.xls --feuille "France entière T1T2" --sortie raw/resultats/interieur/2007-t1t2-definitifs-france.csv` |
| `2007-t2-definitifs-departements.csv` | [b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d4380](https://static.data.gouv.fr/fb/b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d43805a734479294899.xls) | `dfa0fccf37e3c4898427e211e757054c889d9915` | `python outils/interieur_en_csv.py 2007-definitifs.xls --feuille "Départements T2" --sortie raw/resultats/interieur/2007-t2-definitifs-departements.csv` |
| `2012-t1-definitifs-departements.csv` | [e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43](https://static.data.gouv.fr/ff/e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43056790e47bb4f0.xls) | `849947be9597579490ddccce45a7319f822cc85b` | `python outils/interieur_en_csv.py 2012-definitifs.xls --feuille "Départements T1" --sortie raw/resultats/interieur/2012-t1-definitifs-departements.csv` |
| `2012-t1t2-definitifs-france.csv` | [e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43](https://static.data.gouv.fr/ff/e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43056790e47bb4f0.xls) | `849947be9597579490ddccce45a7319f822cc85b` | `python outils/interieur_en_csv.py 2012-definitifs.xls --feuille "France entière T1T2" --sortie raw/resultats/interieur/2012-t1t2-definitifs-france.csv` |
| `2012-t2-definitifs-departements.csv` | [e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43](https://static.data.gouv.fr/ff/e9c9483d39e00030815089aca1e2939f9cb99a84b0136e43056790e47bb4f0.xls) | `849947be9597579490ddccce45a7319f822cc85b` | `python outils/interieur_en_csv.py 2012-definitifs.xls --feuille "Départements T2" --sortie raw/resultats/interieur/2012-t2-definitifs-departements.csv` |
| `2017-t1-definitifs-departements.csv` | [Presidentielle_2017_Resultats_Tour_1_c.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-1er-tour-1/20170427-100131/Presidentielle_2017_Resultats_Tour_1_c.xls) | `d32ec809d89054411b7a2729482fbc9ec1c615a3` | `python outils/interieur_en_csv.py 2017-t1-definitifs.xls --feuille "Départements Tour 1" --sortie raw/resultats/interieur/2017-t1-definitifs-departements.csv` |
| `2017-t1-definitifs-france.csv` | [Presidentielle_2017_Resultats_Tour_1_c.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-1er-tour-1/20170427-100131/Presidentielle_2017_Resultats_Tour_1_c.xls) | `d32ec809d89054411b7a2729482fbc9ec1c615a3` | `python outils/interieur_en_csv.py 2017-t1-definitifs.xls --feuille "FE Metro OM Tour 1" --sortie raw/resultats/interieur/2017-t1-definitifs-france.csv` |
| `2017-t1-provisoires-departements.csv` | [Presidentielle_2017_Resultats_Tour_1.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-du-1er-tour/20170424-095649/Presidentielle_2017_Resultats_Tour_1.xls) | `bb5b7bdfb89aef981e722267cd9b46b2d1df5999` | `python outils/interieur_en_csv.py 2017-t1-provisoires.xls --feuille "Départements Tour 1" --sortie raw/resultats/interieur/2017-t1-provisoires-departements.csv` |
| `2017-t1-provisoires-france.csv` | [Presidentielle_2017_Resultats_Tour_1.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-du-1er-tour/20170424-095649/Presidentielle_2017_Resultats_Tour_1.xls) | `bb5b7bdfb89aef981e722267cd9b46b2d1df5999` | `python outils/interieur_en_csv.py 2017-t1-provisoires.xls --feuille "FE Metro OM Tour 1" --sortie raw/resultats/interieur/2017-t1-provisoires-france.csv` |
| `2017-t2-definitifs-departements.csv` | [Presidentielle_2017_Resultats_Tour_2_c.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-2nd-tour/20170511-092258/Presidentielle_2017_Resultats_Tour_2_c.xls) | `baba058f0be64d2d70c0cc2d67f4539b0c04de37` | `python outils/interieur_en_csv.py 2017-t2-definitifs.xls --feuille "Départements Tour 2" --sortie raw/resultats/interieur/2017-t2-definitifs-departements.csv` |
| `2017-t2-definitifs-france.csv` | [Presidentielle_2017_Resultats_Tour_2_c.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-2nd-tour/20170511-092258/Presidentielle_2017_Resultats_Tour_2_c.xls) | `baba058f0be64d2d70c0cc2d67f4539b0c04de37` | `python outils/interieur_en_csv.py 2017-t2-definitifs.xls --feuille "FE Metro OM Tour 2" --sortie raw/resultats/interieur/2017-t2-definitifs-france.csv` |
| `2017-t2-provisoires-departements.csv` | [Presidentielle_2017_Resultats_Tour_2.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-du-2eme-tour-1/20170508-020951/Presidentielle_2017_Resultats_Tour_2.xls) | `c45c216e76a39d3e39c7c4b71b50c8c17c0a7175` | `python outils/interieur_en_csv.py 2017-t2-provisoires.xls --feuille "Départements Tour 2" --sortie raw/resultats/interieur/2017-t2-provisoires-departements.csv` |
| `2017-t2-provisoires-france.csv` | [Presidentielle_2017_Resultats_Tour_2.xls](https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-du-2eme-tour-1/20170508-020951/Presidentielle_2017_Resultats_Tour_2.xls) | `c45c216e76a39d3e39c7c4b71b50c8c17c0a7175` | `python outils/interieur_en_csv.py 2017-t2-provisoires.xls --feuille "FE Metro OM Tour 2" --sortie raw/resultats/interieur/2017-t2-provisoires-france.csv` |
| `2022-t1-definitifs-departements.csv` | [resultats-par-niveau-dpt-t1-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152356/resultats-par-niveau-dpt-t1-france-entiere.txt) | `a412b9553eec2624e616ef3e411ddf6de7aea9d7` | `python outils/interieur_en_csv.py 2022-t1-definitifs-departements.txt --sortie raw/resultats/interieur/2022-t1-definitifs-departements.csv` |
| `2022-t1-definitifs-france.csv` | [resultats-par-niveau-fe-t1-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152200/resultats-par-niveau-fe-t1-france-entiere.txt) | `e47ede4708fb1481d756efb81eecad6e481f2321` | `python outils/interieur_en_csv.py 2022-t1-definitifs-france.txt --sortie raw/resultats/interieur/2022-t1-definitifs-france.csv` |
| `2022-t1-provisoires-departements.csv` | [resultats-par-niveau-dpt-t1-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-avril-et-24-avril-2022-resultats-du-1er-tour/20220411-110508/resultats-par-niveau-dpt-t1-france-entiere.txt) | `3f689976afe9149961941f59334649b935c44ef0` | `python outils/interieur_en_csv.py 2022-t1-provisoires-departements.txt --sortie raw/resultats/interieur/2022-t1-provisoires-departements.csv` |
| `2022-t1-provisoires-france.csv` | [resultats-par-niveau-fe-t1-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-du-1er-tour/20220411-124802/resultats-par-niveau-fe-t1-france-entiere.txt) | `355d27c5cd53f149f9e391f1c733a03e3897a237` | `python outils/interieur_en_csv.py 2022-t1-provisoires-france.txt --sortie raw/resultats/interieur/2022-t1-provisoires-france.csv` |
| `2022-t2-definitifs-departements.csv` | [resultats-par-niveau-dpt-t2-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-142127/resultats-par-niveau-dpt-t2-france-entiere.txt) | `e28b72f44bbbc751c273ca8b4aa12df4630f84aa` | `python outils/interieur_en_csv.py 2022-t2-definitifs-departements.txt --sortie raw/resultats/interieur/2022-t2-definitifs-departements.csv` |
| `2022-t2-definitifs-france.csv` | [resultats-par-niveau-fe-t2-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-141900/resultats-par-niveau-fe-t2-france-entiere.txt) | `674542e8fa3537fa28a87f1810156d60971535f3` | `python outils/interieur_en_csv.py 2022-t2-definitifs-france.txt --sortie raw/resultats/interieur/2022-t2-definitifs-france.csv` |
| `2022-t2-provisoires-departements.csv` | [resultats-par-niveau-dpt-t2-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-du-second-tour/20220425-100332/resultats-par-niveau-dpt-t2-france-entiere.txt) | `af52ceaa520d6c4be0b4c1ecb74bae2ea79ca455` | `python outils/interieur_en_csv.py 2022-t2-provisoires-departements.txt --sortie raw/resultats/interieur/2022-t2-provisoires-departements.csv` |
| `2022-t2-provisoires-france.csv` | [resultats-par-niveau-fe-t2-france-entiere.txt](https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-du-second-tour/20220425-100100/resultats-par-niveau-fe-t2-france-entiere.txt) | `e57a5115bad154b2ea6b282b055419efcd2210bd` | `python outils/interieur_en_csv.py 2022-t2-provisoires-france.txt --sortie raw/resultats/interieur/2022-t2-provisoires-france.csv` |

Les résultats provisoires sont ceux de la soirée électorale, arrêtés avant que
toutes les commissions de recensement aient fini — « Résultats à 01h30 », dit
la fiche du second tour de 2017. La somme de leurs départements ne fait donc
pas toujours leur total national, et le vote des Français de l'étranger y
manque parfois. Les résultats définitifs, eux, tombent juste, et reprennent à
l'unité près les chiffres proclamés par le Conseil constitutionnel.

Avant 2007, le ministère ne publie rien en données ouvertes. Le jeu
« Élections présidentielles 1965-2012 » du CDSP ne couvre que la métropole
jusqu'en 2002, par circonscription, et ne dit pas si ses chiffres sont ceux du
ministère ou ceux du Journal officiel : il n'est pas repris.
