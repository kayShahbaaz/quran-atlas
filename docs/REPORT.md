# Quran Atlas | أطلس القرآن
## Quranic Semantic Analytics: A Computational Approach to Thematic Exploration

## Abstract

This report documents the methodology, design decisions, and preliminary findings of a computational framework for semantic and thematic analysis of the Noble Quran. Using multilingual sentence embeddings, UMAP dimensionality reduction, and KMeans clustering, a relational model of the Quran's 6,236 Ayaat is constructed that enables thematic exploration beyond traditional keyword search. An interactive web dashboard built with Plotly Dash exposes this model for research and study without requiring programming knowledge.

---

## 1. Motivation

Classical Quranic scholarship has produced extraordinarily rich thematic analyses. They have traces concepts across the text with remarkable depth. What these analyses could not do, constrained by their medium, is provide systematic quantitative views of how themes distribute across the corpus or how their treatment evolves across the chronological sequence of revelation.

Digital Quran tools have largely replicated the keyword search paradigm: enter a word, retrieve Ayaat containing it. This misses the semantic richness of a text where a single concept may be expressed through dozens of morphological forms, where related ideas appear across Surahs without sharing a single word, and where the chronological progression of themes across Meccan and Medinan revelation carries scholarly significance recognized in the tradition of Asbab al-Nuzul and Makkiyya-Madaniyya studies.

This project explores whether modern NLP methods can surface insights complementary to traditional scholarly analysis, while remaining fully grounded in the textual and metadata foundations established by classical scholarship.

---

## 2. Dataset

### 2.1 Primary Text

The primary Arabic text is sourced from Tanzil.net in Simple Unvoweled format. Tanzil is the most widely used digital transcription of the Uthmanic mushaf and is the foundation of the majority of Quran applications and academic research tools globally. The Simple Unvoweled format strips harakat (diacritical marks) and other orthographic embellishments, producing the unambiguous consonantal skeleton on which root word detection and embedding operate.

Corpus statistics:
- 114 Surahs
- 6,236 Ayaat
- Approximately 77,430 Arabic words
- 86 Meccan Surahs containing 4,613 Ayaat (74 percent of total)
- 28 Medinan Surahs containing 1,623 Ayaat (26 percent of total)

### 2.2 Translation

The Sahih International English translation is included alongside the Arabic text. This translation is used in two ways: as part of the bilingual input to the embedding model, and for display in the dashboard interface. The Sahih International translation was selected for its accuracy to the Arabic, its widespread acceptance in English-speaking scholarly and community contexts, and its public domain status.

### 2.3 Revelation Metadata

Surah-level revelation metadata, including Meccan and Medinan classification and chronological revelation order, follows the traditional Islamic scholarly consensus as documented in the classical Ulum al-Quran literature. Where minor variations exist between scholarly positions, the most widely cited ordering is used. This metadata is hardcoded from primary sources rather than derived computationally.

---

## 3. Methodology

### 3.1 Semantic Embeddings

Each Ayah is represented as a 768-dimensional dense vector using the paraphrase-multilingual-mpnet-base-v2 model, accessed via the sentence-transformers library. This model was trained on over 50 million sentence pairs specifically for semantic similarity tasks, making it substantially more appropriate for this application than general-purpose masked language models.

Input format for each Ayah:

```
"{arabic_text} | {english_translation}"
```

Bilingual input was chosen after empirical comparison with English-only and Arabic-only inputs. Arabic-only embedding with general multilingual models produces noisier semantic clusters due to the smaller Arabic subword vocabulary in these models relative to dedicated Arabic models. The English translation provides semantic grounding that compensates for this limitation. English-only embedding was found to produce the best semantic separation for the purposes of thematic search, and is used as the primary mode in this implementation.

All output embeddings are L2-normalized so that cosine similarity equals the dot product, enabling efficient matrix operations at query time.

### 3.2 Dimensionality Reduction

Two UMAP reductions are applied to the 768-dimensional embeddings independently.

For visualization (2D reduction):

```python
umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1, metric="cosine")
```

The min_dist parameter of 0.1 allows visible spread within clusters so that individual points are distinguishable on the scatter plot. This 2D projection is used exclusively for the Theme Map scatter plot.

For clustering (20-dimensional reduction):

```python
umap.UMAP(n_components=20, n_neighbors=15, min_dist=0.0, metric="cosine")
```

A min_dist of 0.0 packs points tightly within their natural clusters, which substantially improves KMeans cluster coherence. Reduction to 20 dimensions retains the majority of the semantic structure present in the original 768-dimensional space while avoiding the curse of dimensionality that would severely degrade KMeans performance at full dimensionality. This 20-dimensional projection is used exclusively for clustering and is not exposed in the dashboard.

### 3.3 Theme Clustering

KMeans clustering is applied to the 20-dimensional UMAP coordinates with K equal to 12. The value of K was selected by running KMeans for K from 8 to 16, examining the elbow curve of inertia against K, and reviewing the Ayah samples in each cluster at candidate values. K=12 produced thematic groupings that corresponded most naturally to the standard academic divisions of Quranic content recognized in the uloom al-Quran tradition.

Cluster label assignment was performed manually by reviewing the 20 highest-confidence Ayaat in each cluster (those closest to the cluster centroid in 20-dimensional space) and assigning a label reflecting the dominant thematic content. This process is inherently interpretive and the resulting labels should be treated as organizational heuristics rather than definitive scholarly conclusions.

The 12 themes are: Divine Attributes and Monotheism, Prophethood and Revelation, Faith and Belief, Worship and Devotion, Ethics and Character, Justice and Law, Economics and Society, Nature and Creation, Historical Narratives, Eschatology and Afterlife, Spiritual and Inner Life, Community and Relations.

### 3.4 Root Word Analysis

Arabic root word detection uses word-boundary aware surface form matching. For each of the 160 roots in the corpus, a curated list of actual surface forms present in the Tanzil Simple Clean text was extracted by scanning all 6,236 Ayaat and collecting every word token for which the root's three consonants appear as an ordered subsequence. Common attached prefixes (and, then, by, for, the, and their combinations) are stripped before matching to handle cliticization.

This approach was adopted after initial implementation using raw substring matching was found to produce significant false positives. In Arabic, the three letters of a root may appear as a coincidental subsequence within words belonging to entirely different roots, and substring matching without word boundaries has no mechanism to distinguish these cases.

### 3.5 Semantic Search

For the Narrative Thread feature, search proceeds as follows. The user's query text is expanded using a curated vocabulary map that adds semantically related terms and Islamic terminology before encoding. The expanded query is encoded using the same model as the Ayah embeddings, producing a 768-dimensional query vector. Cosine similarity between the query vector and all 6,236 Ayah vectors is computed as a single matrix-vector dot product.

A hybrid score is then computed:

```
hybrid_score = 0.85 x semantic_similarity_normalised + 0.15 x keyword_boost
```

The keyword boost is a normalized count of query-related keywords found in the Ayah's English translation. Semantic similarity scores are normalised to the range [0, 1] relative to the minimum and maximum scores in the result set before combining. An adaptive threshold of mean plus k times standard deviation of the hybrid scores filters the result set, where k is tuned per search mode (preset topics versus custom queries).

Results are displayed in chronological revelation order, preserving the Meccan-to-Medinan narrative arc.

For the Ayah Search similarity feature, no query expansion is used: the reference Ayah's pre-computed embedding is used directly as the query vector, and pure cosine similarity ranking is applied.

---

## 4. Preliminary Observations

The following observations emerged from exploratory use of the dashboard. They are presented as preliminary computational findings, not scholarly conclusions. Validation against traditional tafsir literature and Arabic linguistic scholarship would be required before drawing interpretive inferences.

### 4.1 Meccan and Medinan Thematic Distribution

The theme clustering broadly reflects the recognized Meccan-Medinan distinction in Quranic scholarship. Clusters labeled Divine Attributes and Monotheism, Eschatology and Afterlife, and Spiritual and Inner Life show pronounced Meccan concentration. Clusters labeled Justice and Law, Economics and Society, and Community and Relations show Medinan concentration.

This pattern aligns with the scholarly observation that Meccan revelation focuses on foundational theology (tawhid, the afterlife, prophetic narratives establishing the framework of belief) while Medinan revelation addresses community organization, legal rulings, and social ethics. That this pattern emerges from unsupervised machine learning on the text alone, without any scholarly metadata other than the Meccan-Medinan classification, provides some computational corroboration for a well-established scholarly position.

### 4.2 Semantic Cross-Surah Connections

The similarity search surfaces connections that keyword search would not find. Ayaat about water and rain as signs of divine power and prefigurations of resurrection appear clustered together across Al-Baqarah, Al-An'am, Al-Nahl, Al-Hajj, and Qaf despite sharing varying vocabulary. This reflects the Quranic practice of returning to the same theological argument through different specific imagery, a pattern noted extensively in the balagha tradition.

### 4.3 Root Word Distribution Patterns

The root rahm (mercy) appears with roughly equal frequency per Surah across both Meccan and Medinan revelation, confirming its status as a persistent theological theme rather than one concentrated in a particular period. Its appearance in the Basmala, which opens 113 of 114 Surahs, structurally ensures its distribution across the full revelatory timeline.

The root adl (justice and equity) shows a pronounced Medinan concentration, consistent with the shift toward social and legal revelation in Madinah and the establishment of a community requiring legal structures grounded in divine justice.

The root sabr (patience and endurance) shows notable Meccan concentration, particularly in the early Meccan Surahs. This pattern is consistent with the scholarly understanding that patience was the central practical response called for during the period of persecution before the Hijra, when the believers lacked political or military means of response and were instructed to endure.

---

## 5. Limitations

**Morphological analysis.** Surface form matching is an approximation of true Arabic morphological analysis. A production-quality implementation would use a dedicated Arabic morphological analyzer to correctly identify all derived forms of each root and exclude false matches. The current implementation was chosen to avoid dependencies that were unavailable or unstable in the 2021 package environment.

**Embedding model.** The paraphrase-multilingual-mpnet-base-v2 model was trained primarily on European language pairs for general semantic similarity. A model fine-tuned on classical Arabic religious texts would produce more accurate semantic representations for Quranic content.

**Translation dependence.** Including English translation in the embedding input introduces dependence on the interpretive choices of a single translator. Different translation choices would produce different embeddings for the same Arabic text. A more robust approach would average embeddings across multiple translations or develop Arabic-primary representations.

**Cluster subjectivity.** The 12 thematic cluster labels were assigned by reviewing the highest-confidence Ayaat in each cluster. This process reflects one interpretive perspective. Traditional Quranic thematic classification is a complex scholarly discipline with significant variation between scholars, and the computational clusters do not map cleanly onto any single traditional framework.

**Structural repetition.** The Quran contains numerous passages that are structurally repeated across Surahs, most prominently the refrain of Surah Ar-Rahman. These passages form tight semantic clusters based on linguistic form that override their thematic diversity, causing the clustering to reflect textual structure rather than theological content in these cases.

**Basmala handling.** The Basmala appears as Ayah 1:1 and as a non-Ayah prefix to the remaining Surahs except At-Tawbah. The Tanzil dataset includes it only as 1:1, consistent with the majority scholarly position. Its embedding therefore represents only one of its occurrences.

---

## 6. Future Directions

Integration of classical tafsir texts to provide Ayah-level scholarly commentary directly within the dashboard, and to enable validation of cluster assignments against traditional thematic frameworks.

Full Arabic morphological analysis using a dedicated tool to replace the current surface form approach, enabling accurate root detection across all morphological patterns including verb conjugations, verbal nouns, participles, and broken plurals.

BERTopic or similar neural topic modelling approaches that allow soft cluster membership, better reflecting the overlapping thematic nature of Quranic discourse where a single Ayah may simultaneously address theology, ethics, and narrative history.

Cross-reference mapping of the Quran's internal self-references, where one passage directly comments on or elaborates a theme introduced elsewhere, as documented in the traditional science of mutashabihat.

Named entity recognition for prophetic figures, place names, and historical communities to enable entity-level thematic analysis.

Comparison of embedding patterns across multiple English translations to measure the degree to which translation choices affect semantic clustering.

---

## 7. References

Reimers, N. and Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing.

McInnes, L., Healy, J., and Melville, J. (2018). UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction. arXiv:1802.03426.

Devlin, J., Chang, M., Lee, K., and Toutanova, K. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. Proceedings of NAACL-HLT 2019.

Al-Raghib Al-Asfahani (d. 1108 CE). Al-Mufradat fi Gharib al-Quran. Public domain.

Tanzil Project (2007-2022). Digital Quran text repository. tanzil.net.

Dukes, K. (ed.) (2011). The Quranic Arabic Corpus. University of Leeds. corpus.quran.com. GNU Public License.

---

A LearnQuran Academy Project. Quran text from Tanzil.net. Translation: Sahih International.

2019-2022 LearnQuran Academy. All Rights Reserved.

---

**kayShahbaaz خ شهباز**