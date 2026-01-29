"""Semantic Search and Question Answering Service.

Provides semantic search over clinical notes and knowledge graphs with:
- Vector similarity search
- Question answering from clinical context
- Concept relationship queries
- Evidence retrieval with citations
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import threading
import re
import math


# ============================================================================
# Enums and Data Classes
# ============================================================================


class SearchType(Enum):
    """Types of semantic search."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    CONCEPT = "concept"


class QuestionType(Enum):
    """Types of clinical questions."""

    FACTUAL = "factual"  # What medications is patient on?
    TEMPORAL = "temporal"  # When was the last BP reading?
    COMPARATIVE = "comparative"  # How has A1C changed?
    CAUSAL = "causal"  # Why is patient on metformin?
    LIST = "list"  # List all diagnoses
    YES_NO = "yes_no"  # Does patient have diabetes?


@dataclass
class SearchResult:
    """A search result with relevance score."""

    document_id: str
    content: str
    score: float
    section: str | None = None
    highlights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticSearchResponse:
    """Response from semantic search."""

    query: str
    search_type: SearchType
    results: list[SearchResult]
    total_results: int
    search_time_ms: float
    suggestions: list[str] = field(default_factory=list)


@dataclass
class Answer:
    """An answer with evidence."""

    text: str
    confidence: float
    evidence: list[str]
    source_documents: list[str]
    citations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QAResponse:
    """Response from question answering."""

    question: str
    question_type: QuestionType
    answer: Answer
    related_concepts: list[str]
    follow_up_questions: list[str]
    response_time_ms: float


@dataclass
class ConceptRelation:
    """A relationship between concepts."""

    source_concept: str
    relationship: str
    target_concept: str
    evidence: str | None = None
    confidence: float = 1.0


@dataclass
class ConceptSearchResponse:
    """Response from concept relationship search."""

    query_concept: str
    related_concepts: list[ConceptRelation]
    total_relations: int


@dataclass
class IndexedDocument:
    """A document indexed for search."""

    document_id: str
    patient_id: str | None
    content: str
    sections: list[dict[str, str]]  # [{name, content}]
    facts: list[dict[str, Any]]  # Extracted facts
    embedding: list[float] | None = None
    indexed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============================================================================
# Text Processing Utilities
# ============================================================================


def tokenize(text: str) -> list[str]:
    """Simple tokenization."""
    return re.findall(r'\b\w+\b', text.lower())


def compute_tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency."""
    tf = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
    total = len(tokens)
    return {k: v / total for k, v in tf.items()}


def compute_idf(documents: list[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency."""
    n_docs = len(documents)
    df = {}
    for doc in documents:
        seen = set()
        for token in doc:
            if token not in seen:
                df[token] = df.get(token, 0) + 1
                seen.add(token)
    return {k: math.log(n_docs / (v + 1)) + 1 for k, v in df.items()}


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ============================================================================
# Semantic Search and QA Service
# ============================================================================


class SemanticQAService:
    """Service for semantic search and question answering."""

    def __init__(self):
        """Initialize the service."""
        self._documents: dict[str, IndexedDocument] = {}
        self._idf: dict[str, float] = {}
        self._vocab: set[str] = set()
        self._lock = threading.Lock()
        self._question_patterns = self._build_question_patterns()
        self._relation_patterns = self._build_relation_patterns()

    def _build_question_patterns(self) -> dict[QuestionType, list[re.Pattern]]:
        """Build patterns for question classification."""
        return {
            QuestionType.YES_NO: [
                re.compile(r'^(is|does|has|did|was|are|were|do|can|could|should|would)\s', re.I),
            ],
            QuestionType.LIST: [
                re.compile(r'^(list|what are|show|give me|enumerate)\s', re.I),
                re.compile(r'all\s+(the\s+)?(medications|diagnoses|conditions|labs|procedures)', re.I),
            ],
            QuestionType.TEMPORAL: [
                re.compile(r'\b(when|what time|what date|how long|since when|last|recent|latest|first)\b', re.I),
            ],
            QuestionType.COMPARATIVE: [
                re.compile(r'\b(compare|comparison|versus|vs|change|trend|differ|better|worse)\b', re.I),
                re.compile(r'how (has|have|did).*(change|improve|worsen)', re.I),
            ],
            QuestionType.CAUSAL: [
                re.compile(r'\b(why|cause|reason|because|due to|explain)\b', re.I),
            ],
            QuestionType.FACTUAL: [
                re.compile(r'^(what|which|who|where|how much|how many)\s', re.I),
            ],
        }

    def _build_relation_patterns(self) -> list[tuple[str, re.Pattern]]:
        """Build patterns for extracting concept relations."""
        return [
            ("treats", re.compile(r'(\w+)\s+(treats?|for|helps?|manages?)\s+(\w+)', re.I)),
            ("causes", re.compile(r'(\w+)\s+(causes?|leads? to|results? in)\s+(\w+)', re.I)),
            ("contraindicated", re.compile(r'(\w+)\s+(contraindicated|avoid|not for)\s+.*?(\w+)', re.I)),
            ("monitors", re.compile(r'(\w+)\s+(monitors?|checks?|measures?)\s+(\w+)', re.I)),
        ]

    def index_document(
        self,
        document_id: str,
        content: str,
        patient_id: str | None = None,
        sections: list[dict[str, str]] | None = None,
        facts: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Index a document for search.

        Args:
            document_id: Document identifier
            content: Full document text
            patient_id: Optional patient ID
            sections: Optional parsed sections
            facts: Optional extracted facts
        """
        with self._lock:
            # Tokenize and update vocabulary
            tokens = tokenize(content)
            self._vocab.update(tokens)

            # Simple embedding (TF-IDF based for demonstration)
            # In production, use sentence-transformers
            tf = compute_tf(tokens)
            embedding = [tf.get(word, 0) for word in sorted(self._vocab)]

            doc = IndexedDocument(
                document_id=document_id,
                patient_id=patient_id,
                content=content,
                sections=sections or [],
                facts=facts or [],
                embedding=embedding,
            )
            self._documents[document_id] = doc

            # Update IDF
            all_docs = [tokenize(d.content) for d in self._documents.values()]
            self._idf = compute_idf(all_docs)

    def search(
        self,
        query: str,
        search_type: SearchType = SearchType.HYBRID,
        patient_id: str | None = None,
        max_results: int = 10,
        min_score: float = 0.1,
    ) -> SemanticSearchResponse:
        """
        Search indexed documents.

        Args:
            query: Search query
            search_type: Type of search
            patient_id: Filter by patient
            max_results: Maximum results to return
            min_score: Minimum relevance score

        Returns:
            Search response with results
        """
        import time
        start = time.time()

        results = []

        with self._lock:
            # Filter by patient if specified
            docs = list(self._documents.values())
            if patient_id:
                docs = [d for d in docs if d.patient_id == patient_id]

            if search_type == SearchType.KEYWORD:
                results = self._keyword_search(query, docs)
            elif search_type == SearchType.SEMANTIC:
                results = self._semantic_search(query, docs)
            else:  # HYBRID
                keyword_results = self._keyword_search(query, docs)
                semantic_results = self._semantic_search(query, docs)
                results = self._merge_results(keyword_results, semantic_results)

        # Filter and sort
        results = [r for r in results if r.score >= min_score]
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:max_results]

        # Generate suggestions
        suggestions = self._generate_suggestions(query, results)

        search_time = (time.time() - start) * 1000

        return SemanticSearchResponse(
            query=query,
            search_type=search_type,
            results=results,
            total_results=len(results),
            search_time_ms=round(search_time, 2),
            suggestions=suggestions,
        )

    def _keyword_search(
        self,
        query: str,
        docs: list[IndexedDocument],
    ) -> list[SearchResult]:
        """Perform keyword search."""
        query_tokens = set(tokenize(query))
        results = []

        for doc in docs:
            doc_tokens = set(tokenize(doc.content))
            overlap = query_tokens & doc_tokens

            if overlap:
                # Simple TF-IDF scoring
                score = 0.0
                for token in overlap:
                    tf = doc.content.lower().count(token) / len(doc.content.split())
                    idf = self._idf.get(token, 1.0)
                    score += tf * idf

                # Extract highlights
                highlights = []
                for token in overlap:
                    pattern = re.compile(rf'\b.{{0,30}}{re.escape(token)}.{{0,30}}\b', re.I)
                    matches = pattern.findall(doc.content)
                    highlights.extend(matches[:2])

                results.append(SearchResult(
                    document_id=doc.document_id,
                    content=doc.content[:500],
                    score=min(score, 1.0),
                    highlights=highlights[:3],
                    metadata={"patient_id": doc.patient_id},
                ))

        return results

    def _semantic_search(
        self,
        query: str,
        docs: list[IndexedDocument],
    ) -> list[SearchResult]:
        """Perform semantic similarity search."""
        query_tokens = tokenize(query)
        query_tf = compute_tf(query_tokens)

        # Create query embedding
        query_embedding = [
            query_tf.get(word, 0) * self._idf.get(word, 1.0)
            for word in sorted(self._vocab)
        ]

        results = []
        for doc in docs:
            if doc.embedding:
                # Pad embeddings to same length
                doc_emb = doc.embedding + [0] * (len(query_embedding) - len(doc.embedding))
                query_emb = query_embedding + [0] * (len(doc.embedding) - len(query_embedding))

                score = cosine_similarity(query_emb[:len(doc_emb)], doc_emb[:len(query_emb)])

                if score > 0:
                    results.append(SearchResult(
                        document_id=doc.document_id,
                        content=doc.content[:500],
                        score=score,
                        metadata={"patient_id": doc.patient_id},
                    ))

        return results

    def _merge_results(
        self,
        keyword_results: list[SearchResult],
        semantic_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Merge keyword and semantic results."""
        merged: dict[str, SearchResult] = {}

        for r in keyword_results:
            merged[r.document_id] = r

        for r in semantic_results:
            if r.document_id in merged:
                # Combine scores
                merged[r.document_id].score = (merged[r.document_id].score + r.score) / 2
            else:
                merged[r.document_id] = r

        return list(merged.values())

    def _generate_suggestions(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[str]:
        """Generate search suggestions."""
        suggestions = []

        # Suggest related terms from results
        if results:
            all_tokens = []
            for r in results[:3]:
                all_tokens.extend(tokenize(r.content))

            # Find frequent terms not in query
            query_tokens = set(tokenize(query))
            term_counts: dict[str, int] = {}
            for token in all_tokens:
                if token not in query_tokens and len(token) > 3:
                    term_counts[token] = term_counts.get(token, 0) + 1

            top_terms = sorted(term_counts.items(), key=lambda x: -x[1])[:3]
            suggestions = [f"{query} {term}" for term, _ in top_terms]

        return suggestions

    def answer_question(
        self,
        question: str,
        patient_id: str | None = None,
        context: str | None = None,
    ) -> QAResponse:
        """
        Answer a clinical question.

        Args:
            question: The question to answer
            patient_id: Patient context
            context: Additional context

        Returns:
            QA response with answer and evidence
        """
        import time
        start = time.time()

        # Classify question type
        question_type = self._classify_question(question)

        # Search for relevant context
        search_response = self.search(
            question,
            SearchType.HYBRID,
            patient_id=patient_id,
            max_results=5,
        )

        # Build context from search results
        if context:
            full_context = context
        else:
            full_context = "\n\n".join([r.content for r in search_response.results])

        # Generate answer based on question type
        answer = self._generate_answer(question, question_type, full_context, search_response.results)

        # Find related concepts
        related_concepts = self._extract_related_concepts(full_context, question)

        # Generate follow-up questions
        follow_ups = self._generate_follow_up_questions(question, answer.text, question_type)

        response_time = (time.time() - start) * 1000

        return QAResponse(
            question=question,
            question_type=question_type,
            answer=answer,
            related_concepts=related_concepts,
            follow_up_questions=follow_ups,
            response_time_ms=round(response_time, 2),
        )

    def _classify_question(self, question: str) -> QuestionType:
        """Classify the type of question."""
        for q_type, patterns in self._question_patterns.items():
            for pattern in patterns:
                if pattern.search(question):
                    return q_type
        return QuestionType.FACTUAL

    def _generate_answer(
        self,
        question: str,
        question_type: QuestionType,
        context: str,
        results: list[SearchResult],
    ) -> Answer:
        """Generate answer from context."""
        # Extract key terms from question
        question_tokens = set(tokenize(question))
        clinical_terms = ["medication", "diagnosis", "condition", "lab", "vital", "procedure",
                         "blood pressure", "a1c", "glucose", "weight", "pain"]

        # Find relevant sentences
        sentences = re.split(r'[.!?]', context)
        relevant_sentences = []

        for sentence in sentences:
            sentence_tokens = set(tokenize(sentence))
            overlap = question_tokens & sentence_tokens
            if overlap or any(term in sentence.lower() for term in clinical_terms if term in question.lower()):
                relevant_sentences.append(sentence.strip())

        # Build answer based on question type
        if question_type == QuestionType.YES_NO:
            answer_text = self._answer_yes_no(question, relevant_sentences)
        elif question_type == QuestionType.LIST:
            answer_text = self._answer_list(question, relevant_sentences)
        elif question_type == QuestionType.TEMPORAL:
            answer_text = self._answer_temporal(question, relevant_sentences)
        else:
            answer_text = self._answer_factual(question, relevant_sentences)

        # Calculate confidence
        confidence = min(len(relevant_sentences) / 5, 1.0) if relevant_sentences else 0.3

        # Build citations
        citations = [
            {
                "document_id": r.document_id,
                "excerpt": r.content[:200],
                "relevance": r.score,
            }
            for r in results[:3]
        ]

        return Answer(
            text=answer_text,
            confidence=confidence,
            evidence=relevant_sentences[:5],
            source_documents=[r.document_id for r in results],
            citations=citations,
        )

    def _answer_yes_no(self, question: str, sentences: list[str]) -> str:
        """Generate yes/no answer."""
        if not sentences:
            return "I couldn't find enough information to answer definitively."

        # Look for affirmative/negative patterns
        affirmative = ["has", "is", "does", "diagnosed", "taking", "positive", "confirmed"]
        negative = ["no", "not", "negative", "denied", "absent", "without"]

        aff_count = sum(1 for s in sentences for a in affirmative if a in s.lower())
        neg_count = sum(1 for s in sentences for n in negative if n in s.lower())

        if aff_count > neg_count:
            return f"Yes, based on the available information. {sentences[0]}"
        elif neg_count > aff_count:
            return f"No, based on the available information. {sentences[0]}"
        else:
            return f"The information is inconclusive. Relevant context: {sentences[0]}"

    def _answer_list(self, question: str, sentences: list[str]) -> str:
        """Generate list answer."""
        if not sentences:
            return "No relevant items found."

        # Extract items (simple approach)
        items = []
        for sentence in sentences:
            # Look for list-like patterns
            parts = re.split(r'[,;]', sentence)
            for part in parts:
                part = part.strip()
                if len(part) > 3 and len(part) < 100:
                    items.append(part)

        if items:
            unique_items = list(dict.fromkeys(items))[:10]
            return "Found the following:\n• " + "\n• ".join(unique_items)
        else:
            return f"Based on the records: {sentences[0]}"

    def _answer_temporal(self, question: str, sentences: list[str]) -> str:
        """Generate temporal answer."""
        if not sentences:
            return "No temporal information found."

        # Look for dates and times
        date_pattern = re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.I)

        for sentence in sentences:
            dates = date_pattern.findall(sentence)
            if dates:
                return f"Based on the records: {sentence}"

        return f"Temporal context from records: {sentences[0]}"

    def _answer_factual(self, question: str, sentences: list[str]) -> str:
        """Generate factual answer."""
        if not sentences:
            return "I couldn't find specific information to answer this question."

        return f"Based on the clinical records: {sentences[0]}"

    def _extract_related_concepts(self, context: str, question: str) -> list[str]:
        """Extract related clinical concepts."""
        # Common clinical concept patterns
        concept_patterns = [
            r'\b(diabetes|hypertension|asthma|copd|chf|cad|ckd|depression|anxiety)\b',
            r'\b(metformin|lisinopril|aspirin|insulin|atorvastatin|omeprazole)\b',
            r'\b(a1c|creatinine|hemoglobin|glucose|potassium|sodium)\b',
        ]

        concepts = set()
        for pattern in concept_patterns:
            matches = re.findall(pattern, context.lower())
            concepts.update(matches)

        # Remove concepts already in question
        question_lower = question.lower()
        concepts = {c for c in concepts if c not in question_lower}

        return list(concepts)[:5]

    def _generate_follow_up_questions(
        self,
        question: str,
        answer: str,
        question_type: QuestionType,
    ) -> list[str]:
        """Generate follow-up questions."""
        follow_ups = []

        if question_type == QuestionType.YES_NO:
            follow_ups.append(f"When was this first documented?")
            follow_ups.append(f"What is the current status?")
        elif question_type == QuestionType.LIST:
            follow_ups.append(f"Which of these is most recent?")
            follow_ups.append(f"Are there any changes to this list?")
        elif question_type == QuestionType.TEMPORAL:
            follow_ups.append(f"What was the value at that time?")
            follow_ups.append(f"How has this changed since then?")
        else:
            follow_ups.append(f"What are the related conditions?")
            follow_ups.append(f"What is the treatment plan?")

        return follow_ups[:3]

    def search_concept_relations(
        self,
        concept: str,
        patient_id: str | None = None,
    ) -> ConceptSearchResponse:
        """
        Search for relationships involving a concept.

        Args:
            concept: The concept to search for
            patient_id: Optional patient filter

        Returns:
            Concept relations found
        """
        relations = []

        with self._lock:
            docs = list(self._documents.values())
            if patient_id:
                docs = [d for d in docs if d.patient_id == patient_id]

            for doc in docs:
                # Search in extracted facts
                for fact in doc.facts:
                    if concept.lower() in fact.get("label", "").lower():
                        # Look for related facts
                        for other_fact in doc.facts:
                            if other_fact != fact:
                                relation = self._infer_relation(fact, other_fact)
                                if relation:
                                    relations.append(relation)

                # Search using patterns
                for rel_type, pattern in self._relation_patterns:
                    matches = pattern.findall(doc.content)
                    for match in matches:
                        if concept.lower() in match[0].lower() or concept.lower() in match[2].lower():
                            relations.append(ConceptRelation(
                                source_concept=match[0],
                                relationship=rel_type,
                                target_concept=match[2],
                                evidence=doc.document_id,
                            ))

        # Deduplicate
        seen = set()
        unique_relations = []
        for r in relations:
            key = (r.source_concept, r.relationship, r.target_concept)
            if key not in seen:
                seen.add(key)
                unique_relations.append(r)

        return ConceptSearchResponse(
            query_concept=concept,
            related_concepts=unique_relations[:20],
            total_relations=len(unique_relations),
        )

    def _infer_relation(
        self,
        fact1: dict[str, Any],
        fact2: dict[str, Any],
    ) -> ConceptRelation | None:
        """Infer relationship between two facts."""
        type1 = fact1.get("fact_type", "")
        type2 = fact2.get("fact_type", "")

        if type1 == "condition" and type2 == "drug":
            return ConceptRelation(
                source_concept=fact2.get("label", ""),
                relationship="treats",
                target_concept=fact1.get("label", ""),
            )
        elif type1 == "drug" and type2 == "condition":
            return ConceptRelation(
                source_concept=fact1.get("label", ""),
                relationship="treats",
                target_concept=fact2.get("label", ""),
            )
        elif type1 == "measurement" and type2 == "condition":
            return ConceptRelation(
                source_concept=fact1.get("label", ""),
                relationship="monitors",
                target_concept=fact2.get("label", ""),
            )

        return None

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                "indexed_documents": len(self._documents),
                "vocabulary_size": len(self._vocab),
                "search_types": [st.value for st in SearchType],
                "question_types": [qt.value for qt in QuestionType],
            }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: SemanticQAService | None = None
_service_lock = threading.Lock()


def get_semantic_qa_service() -> SemanticQAService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = SemanticQAService()

    return _service_instance


def reset_semantic_qa_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
