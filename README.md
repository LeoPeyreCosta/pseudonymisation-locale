# Pseudonymisation locale

[![Tests](https://github.com/LeoPeyreCosta/pseudonymisation-locale/actions/workflows/tests.yml/badge.svg)](https://github.com/LeoPeyreCosta/pseudonymisation-locale/actions/workflows/tests.yml)

Masquer les données personnelles d'un document français (lettre de liaison,
compte rendu, note sociale, courriel RH, réclamation d'usager) **sans
l'envoyer à un service en ligne**. Les données à format connu sont repérées
par des règles vérifiables ; les noms de personnes, de lieux et
d'organisations par un modèle de langue qui tourne sur la machine, via
[Ollama](https://ollama.com).

## Le problème

Un hôpital, un service social ou une mairie a souvent besoin de sortir un
document de son contexte d'origine : le transmettre à un prestataire,
l'utiliser pour une formation, un audit ou un outil d'analyse. Le RGPD
demande de limiter les données au nécessaire (article 5) et cite la
pseudonymisation parmi les mesures de protection (articles 25 et 32).

Masquer à la main est lent et laisse passer des oublis. Confier le document à
un service d'IA en ligne pour le faire revient à transmettre précisément les
données qu'on cherche à protéger. Cet outil fait le travail en local et
mesure ce qu'il laisse passer.

## Exemple (sortie réelle)

Extrait d'un document fictif du corpus, traité avec
`pseudonymiser traiter corpus/developpement/1_lettre_liaison.txt`
(mistral 7B, 5 s) :

```text
Centre hospitalier des Trois Fontaines
Service de cardiologie
Montpellier, le 14 octobre 2026

Dr Hélène Varenne
Tél. : 04 65 71 58 21
Courriel : h.varenne@ch-troisfontaines.example

À l'attention du Dr Bruno Lesage, médecin traitant
12 rue des Tisserands, 34170 Castelnau-le-Lez

Objet : Mme Josiane Ferrand, née le 03/02/1951
IPP : 20481739
N° de sécurité sociale : 2 51 02 34 172 045 40

[…] Mme Ferrand décrit une dyspnée d'effort stable et un bon respect du
traitement. Son fils, Thierry Ferrand, l'accompagnait et confirme une bonne
autonomie à domicile. […] Josiane souhaite rester suivie à Montpellier.
```

devient :

```text
[ORGANISATION_1]
Service de cardiologie
[LIEU_1], le [DATE_1]

Dr [PERSONNE_1]
Tél. : [TELEPHONE_1]
Courriel : [EMAIL_1]

À l'attention du [PERSONNE_2], médecin traitant
[ADRESSE_1]

Objet : Mme [PERSONNE_3], née le [DATE_2]
IPP : [IDENTIFIANT_1]
N° de sécurité sociale : [NIR_1]

[…] Mme [PERSONNE_3] décrit une dyspnée d'effort stable et un bon respect du
traitement. Son fils, Thierry [PERSONNE_3], l'accompagnait et confirme une bonne
autonomie à domicile. […] [PERSONNE_3] souhaite rester suivie à [LIEU_1].
```

Une table de correspondance (`.table.json`, à conserver à part) permet de
revenir au texte d'origine : `[PERSONNE_3]` → « Josiane Ferrand »,
« Ferrand », « Josiane ».

L'exemple montre aussi une erreur : le modèle n'a pas repéré « Thierry
Ferrand ». Son nom de famille est masqué (il a été appris sur « Josiane
Ferrand »), mais le prénom reste lisible et reçoit l'étiquette de sa mère.
C'est le type d'oubli que l'évaluation ci-dessous cherche à mesurer, et la
raison pour laquelle une relecture reste nécessaire.

## Fonctionnement

```text
  Document (.txt, .md, .pdf)
        │
        ├──► Règles (regles.py)                    déterministes, vérifiables
        │      NIR avec clé, IBAN (mod 97), courriels, téléphones, dates,
        │      adresses et compléments, identifiants (IPP, RPPS, matricule…),
        │      champs « Nom : » / « Prénom : »
        │
        ├──► Modèle local (llm.py)                 Ollama, localhost:11434
        │      personnes, lieux, organisations
        │      sortie imposée par un schéma JSON, température 0
        │        │
        │        ▼
        │    Garde-fous
        │      la mention doit figurer dans le texte (sinon : rejetée)
        │      propositions invraisemblables écartées (« Dr » seul, « si douleur »)
        │      « Mme Ferrand », « Josiane » reliées à « Josiane Ferrand »
        │
        ▼
  Arbitrage des chevauchements (fusion.py)   les règles l'emportent
        │
        ▼
  Remplacement (remplacement.py)
      [PERSONNE_1], [DATE_2]… + table de correspondance
      ou, avec --anonymiser : [PERSONNE], [DATE]… sans table
```

Quelques choix :

- **Règles d'abord.** Un IBAN n'est retenu que si sa clé de contrôle est
  juste ; un NIR, si sa clé est juste ou si le texte qui précède annonce un
  numéro de sécurité sociale. Ce qui a une structure ne dépend pas du
  modèle.
- **Le modèle propose, le code décide.** Une proposition qui ne figure pas
  dans le texte est écartée : le modèle ne peut pas faire masquer un mot
  inventé. S'il réordonne un nom (« Rémi Tessier » pour « TESSIER Rémi »),
  les mots sont recherchés dans l'autre ordre.
- **Tout le document.** Le texte est envoyé au modèle par blocs d'environ
  1 500 caractères, mais un nom repéré dans un bloc est masqué partout.
- **Même personne, même étiquette.** Les formes courtes d'un nom reçoivent
  l'étiquette de l'identité complète, ce qui garde le texte lisible.

## Garanties

- **Aucun envoi hors du poste.** Le code ne contacte que le serveur Ollama
  indiqué par `--url` (par défaut `http://localhost:11434`) : `/api/tags`
  pour vérifier qu'il répond, `/api/chat` pour l'analyse. Pas de clé d'API,
  pas de service tiers, pas de télémétrie. Si `--url` désigne une autre
  machine, les documents y transitent : à réserver à un serveur maîtrisé.
- **Sans modèle, ça marche quand même.** `--sans-llm` applique les règles
  seules, sans GPU (les noms ne sont alors pas détectés).
- **Sorties hors du dépôt.** Le `.gitignore` exclut `documents/`,
  `sorties/`, `*.table.json` et `*.pseudonymise.txt`.

Ce que l'outil ne garantit pas : un masquage complet. Voir l'évaluation et
les limites.

## Évaluation

Les mesures portent sur des documents fictifs annotés à la main (voir
[`corpus/README.md`](corpus/README.md) pour le guide d'annotation) :

- **rappel** : part des données annotées entièrement masquées, quel que soit
  le type attribué. Ce qui n'est pas masqué fuit ; c'est l'indicateur qui
  compte pour la protection des personnes ;
- **précision** : part des masquages qui ne couvrent que des données
  personnelles (une civilité masquée avec le nom est tolérée). Un masquage
  inutile gêne la lecture mais ne fait courir aucun risque.

Deux corpus : `developpement/` (6 documents, 95 occurrences) a servi à
mettre au point les règles et les garde-fous ; ses chiffres sont donc
optimistes. `controle/` (4 documents, 60 occurrences) a été écrit et versé
après le gel du code (commit `7609643`), puis mesuré.

### Code actuel

| Configuration | Développement (95) | Contrôle (60) |
|---|---|---|
| Règles seules (`--sans-llm`) | rappel 51,6 %, précision 100 % | rappel 50,0 %, précision 100 % |
| mistral 7B seul (`--sans-regles`) | rappel 68,4 %, précision 86,4 % | rappel 55,0 %, précision 97,6 % |
| Règles + mistral 7B | rappel 97,9 %, précision 91,1 % | rappel 93,3 à 96,7 %, précision 100 % |

**Aucune des deux parties ne suffit seule.** Les règles ne trouvent aucun
nom ; le modèle seul ne masque aucun numéro de sécurité sociale et presque
aucun téléphone ni courriel, et manque la plupart des dates (6 sur 16, puis
1 sur 11). Il en propose parfois, mais étiquetés comme des lieux, et le
filtre de plausibilité les écarte : ce filtre est conçu pour l'outil complet,
où les règles couvrent ces données. La ligne « modèle seul » provient d'un
seul passage.

### Historique du corpus de contrôle

| Mesure | Rappel | Précision |
|---|---|---|
| Première mesure, code gelé (`7609643`) | 81,7 à 85,0 % | 100 % |
| Après les corrections tirées de cette mesure (`7d17662`, `a8ccd56`) | 93,3 à 96,7 % | 100 % |

La première mesure a montré des fuites que le code pouvait éviter : noms en
minuscules dans un formulaire (« Nom : martineau »), date sans année,
« chambre 214 », ville citée seule alors qu'elle figurait dans une adresse,
nom réordonné par le modèle. Elles ont été corrigées par des règles
générales, testées à part. La seconde ligne n'est donc plus une mesure
indépendante : elle montre l'effet des corrections, pas la performance
attendue sur un document nouveau, qui se situe plus probablement entre les
deux.

**Variabilité.** Même à température 0, les réponses du modèle varient
légèrement d'un passage à l'autre : sur le contrôle, le premier passage
après le chargement du modèle et les suivants diffèrent d'une ou deux
mentions. Les fourchettes couvrent au moins 4 passages par configuration,
dont au moins un juste après le chargement du modèle. Sur le corpus de
développement, tous les passages ont donné le même résultat.

**Fuites restantes** (code actuel) : « Mutuelle Garrigue Santé » et
« Pauline Meunier » (contrôle, à chaque passage), « CCAS de Pignan » et
« Laetitia Roux » (contrôle, au premier passage après chargement), le
prénom de « Thierry Ferrand » et « Saint-Clair-du-Lez » cité seul
(développement). Toutes viennent d'oublis du modèle.

**Masquages inutiles** (développement) : noms de services (« Service
relations usagers »), médicaments (« Amoxicilline 1 g »), sigle « CAF »,
rubrique « Renouvellement », et deux masquages qui débordent (« (épouse) »
pris avec le nom, « association » avec « Entraide Hérault »).

Une consigne plus détaillée pour le modèle (fonctions, médicaments,
rubriques à ignorer) a été essayée : elle faisait baisser le rappel sur le
corpus de développement (95,8 % au lieu de 97,9 %). La consigne d'origine a
été gardée.

Pour reproduire :

```sh
pseudonymiser evaluer corpus/controle --details
pseudonymiser evaluer corpus/controle --sans-llm      # règles seules
pseudonymiser evaluer corpus/controle --sans-regles   # modèle seul
```

## Installation

Prérequis : Python 3.10 ou plus récent, et [Ollama](https://ollama.com) pour
la détection des noms.

```sh
git clone https://github.com/LeoPeyreCosta/pseudonymisation-locale.git
cd pseudonymisation-locale
python -m pip install -e ".[pdf]"
ollama pull mistral
```

## Utilisation

```sh
# Pseudonymiser : texte traité + table de correspondance
pseudonymiser traiter courrier.txt

# Étiquettes génériques, sans table
pseudonymiser traiter courrier.txt --anonymiser

# Règles seules, sans modèle ni GPU
pseudonymiser traiter courrier.pdf --sans-llm

# Autre modèle installé dans Ollama (seul mistral a été évalué ici)
pseudonymiser traiter courrier.txt --modele NOM_DU_MODELE --details
```

Depuis Python :

```python
from pseudonymiseur import ClientOllama, traiter

traitement = traiter(texte, client=ClientOllama(modele="mistral"))
print(traitement.resultat.texte)   # texte pseudonymisé
print(traitement.resultat.table)   # étiquette → formes d'origine
```

## Limites

- **Les corpus sont petits et fictifs**, écrits par l'auteur de l'outil.
  Les chiffres servent à repérer des erreurs et à comparer des réglages, pas
  à annoncer un taux de fiabilité. Sur des documents réels, plus variés, il
  faut s'attendre à davantage d'oublis.
- **Le modèle oublie des mentions**, et pas toujours les mêmes d'un passage
  à l'autre. Un prénom isolé non relié à une identité connue fuit ; un nom
  de famille partagé reçoit l'étiquette du premier membre de la famille
  repéré.
- **Les quasi-identifiants ne sont pas traités** : âge, profession,
  maladie rare, événement daté sans date précise. Recoupés, ils peuvent
  suffire à reconnaître quelqu'un.
- **Formats français** pour le téléphone et le NIR ; l'IBAN est vérifié quel
  que soit le pays.
- **PDF** : seul le texte numérique est lu. Un document scanné doit d'abord
  passer par une reconnaissance de caractères.
- **Pseudonymiser n'est pas anonymiser.** Au sens du RGPD (considérant 26),
  un document pseudonymisé reste une donnée personnelle ; la table de
  correspondance est elle-même sensible. Le mode `--anonymiser` supprime la
  table, mais ne garantit pas à lui seul qu'on ne peut plus reconnaître les
  personnes à partir du contexte.

Une relecture humaine reste indispensable avant toute diffusion.

## Matériel

Mesures faites sur :

- carte graphique NVIDIA RTX 3080 (10 Go), Windows 11, Python 3.13 ;
- Ollama 0.40.12, `mistral` 7B quantifié (Q4_K_M) : 4,4 Go sur disque,
  environ 4,6 Go de mémoire graphique une fois chargé ;
- environ 5 secondes par document d'une page (31 s pour les 6 documents du
  corpus de développement).

Le modèle occupant environ 4,6 Go, une carte de 8 Go devrait suffire (non
testé). Sans carte graphique, Ollama fonctionne sur le processeur, plus
lentement (non mesuré ici). Les tests unitaires n'ont besoin ni de GPU ni de modèle : ils utilisent
un faux client et tournent dans la CI sur Python 3.10 à 3.13.

## Structure

```text
src/pseudonymiseur/
  regles.py         détection par règles (NIR, IBAN, dates, adresses…)
  llm.py            client Ollama, consigne, garde-fous, liaison des noms
  fusion.py         arbitrage des détections qui se chevauchent
  remplacement.py   étiquettes et table de correspondance
  pipeline.py       enchaînement complet
  evaluation.py     rappel, précision, fuites
  __main__.py       ligne de commande
tests/              tests unitaires (sans modèle)
corpus/             documents fictifs annotés et guide d'annotation
```

## Tests et qualité

```sh
python -m pip install -e ".[dev]"
python -m pytest --cov
```

50 tests, sans GPU ni Ollama : un faux client remplace le modèle, et le
contrat avec Ollama (schéma JSON, température, contenu de la requête) est
vérifié sur une réponse simulée. La CI (Python 3.10 à 3.13) exécute aussi
une analyse statique (pyflakes), une vérification des types (mypy) et exige
au moins 85 % de couverture (88 % aujourd'hui).

## Projets liés

Quatre outils d'IA locale, construits et évalués de la même façon (corpus
fictifs annotés, corpus de contrôle versé avant la mesure) :

- [rag-local-souverain](https://github.com/LeoPeyreCosta/rag-local-souverain) :
  interroger ses documents internes, avec une interface web accessible ;
- [tri-demandes-local](https://github.com/LeoPeyreCosta/tri-demandes-local) :
  orienter les demandes d'usagers d'une mairie et repérer les urgences ;
- [compte-rendu-local](https://github.com/LeoPeyreCosta/compte-rendu-local) :
  transcrire une réunion et en rédiger le compte rendu ;
- pseudonymisation-locale (ce dépôt).

## Licence

MIT
