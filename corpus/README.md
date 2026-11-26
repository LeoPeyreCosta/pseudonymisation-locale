# Corpus d'évaluation

Documents français fictifs, annotés à la main, qui servent à mesurer ce que
l'outil masque et ce qu'il laisse passer.

## Données fictives

- Les personnes, les situations et les numéros sont inventés.
- Les communes sont réelles. Les établissements sont imaginés : une homonymie
  avec un établissement existant serait fortuite.
- Les numéros de sécurité sociale et les IBAN ont une clé de contrôle valide,
  pour que les règles qui vérifient cette clé soient réellement mises à
  l'épreuve. Ils ont été composés pour l'occasion ; les IBAN utilisent les
  codes banque 99998 et 99999.
- Les adresses électroniques utilisent le domaine `.example`, réservé à la
  documentation (RFC 2606).

Ne déposez jamais de document réel dans ce dossier.

## Deux sous-corpus

| Dossier | Documents | Occurrences annotées | Rôle |
|---|---:|---:|---|
| `developpement/` | 6 | 95 | mise au point des règles et du filtrage des propositions du modèle |
| `controle/` | 4 | 60 | contrôle : écrit et annoté après le gel du code, évalué tel quel |

Les chiffres obtenus sur `developpement/` sont optimistes par construction :
les erreurs qu'on y a vues ont été corrigées. Ceux de `controle/` donnent une
meilleure idée du comportement sur un document nouveau. L'historique git
montre que le corpus de contrôle a été versé après les derniers changements
du code de détection.

Les deux corpus restent très petits : ils permettent de repérer des erreurs et
de comparer des réglages, pas d'annoncer un taux de fiabilité général.

## Format

Chaque document `nom.txt` est accompagné de `nom.annotations.json`, la liste
des données personnelles qu'il contient :

```json
[
  {"texte": "Josiane Ferrand", "type": "PERSONNE"},
  {"texte": "Ferrand", "type": "PERSONNE"}
]
```

Une annotation désigne toutes les occurrences exactes de ce texte dans le
document (mots entiers, majuscules respectées, espaces et retours à la ligne
indifférents). Une occurrence comprise dans une occurrence annotée plus longue
(« Ferrand » dans « Josiane Ferrand ») n'est comptée qu'une fois, avec la plus
longue. Une annotation introuvable dans le texte fait échouer l'évaluation.

## Guide d'annotation

Principe : on annote ce qui permet, seul ou recoupé avec le reste du
document, de retrouver une personne.

| Type | Ce qu'on annote | Exemples |
|---|---|---|
| `PERSONNE` | prénom et nom, sans la civilité ; chaque forme courte employée seule est annotée à part. Enfants, proches et professionnels compris. | « Josiane Ferrand », puis « Ferrand » et « Josiane » ; « martineau » tel qu'écrit |
| `ADRESSE` | l'adresse postale d'un seul tenant : complément (résidence, bâtiment, appartement), voie, code postal, ville. Un nom de voie cité seul ou une localisation dans un établissement en sont aussi. | « Résidence Les Hirondelles, bâtiment C, 4 allée des Genêts, 34080 Montpellier » ; « chemin de la Garrigue » ; « chambre 214 » |
| `LIEU` | commune ou quartier cité hors d'une adresse. Si la ville suit la voie après une préposition, la voie est une `ADRESSE` et la ville un `LIEU`. | « Montpellier, le 14 octobre » ; « 3 rue du Moulin a Pignan » |
| `ORGANISATION` | établissement fréquenté par la personne (hôpital, école, employeur, mairie, mutuelle, association), dans sa désignation complète, terme générique compris quand il fait partie du nom, mais pas quand il n'est qu'un descriptif. | « Clinique des Garrigues », « école Jules-Ferry », « centre médico-social de la Mosson » ; « l'association Entraide Hérault » → « Entraide Hérault » |
| `DATE` | toute date précise, avec ou sans année, sans l'article. | « 9 octobre 2026 », « 03/02/1951 », « 2 novembre » |
| `EMAIL`, `TELEPHONE`, `NIR`, `IBAN` | la valeur telle qu'écrite. | « 06 39 98 41 07 », « 0639984512 » |
| `IDENTIFIANT` | la valeur seule, sans son libellé. | « 20481739 » dans « IPP : 20481739 » |

Ne sont pas annotés, par choix :

- les organismes nationaux qui ne désignent personne en particulier (CAF,
  CPAM) ;
- les fonctions et les services (« médecin traitant », « Service de
  cardiologie ») ;
- les âges, classes, heures et montants. Ce sont pourtant des
  quasi-identifiants : l'outil ne les traite pas, c'est une limite connue.

## Modifications après une première mesure

Le document 4 du corpus de développement a été corrigé après une première
évaluation, pour appliquer le guide ci-dessus de façon cohérente avec les
autres documents : l'adresse est annotée d'un seul tenant (résidence et
bâtiment compris), « école Jules-Ferry » et « centre médico-social de la
Mosson » en désignation complète. Ces corrections ont été faites en
connaissant les sorties du modèle ; c'est une raison de plus de lire les
chiffres du corpus de développement avec prudence.
