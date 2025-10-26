"""
RAG System for code context retrieval with enhanced logging
"""
from typing import List, Dict, Optional
import json
from pathlib import Path
from datetime import datetime
import hashlib
from logger import get_app_logger

logger = get_app_logger("rag_system")

class RAGSystem:
    """Simple RAG system for code context retrieval"""
    
    def __init__(self):
        self.storage_dir = Path("rag_storage")
        self.storage_dir.mkdir(exist_ok=True)
        
        # In-memory storage for quick access
        self.code_documents = {}
        self.embeddings = {}
        self.metadata = {}
        
        logger.info(" RAG System initialized")
        logger.info(f" Storage directory: {self.storage_dir.absolute()}")
        
        # Load existing data
        self._load_storage()
    
    def add_code_documents(self, parsed_data: Dict[str, Dict]):
        """
        Add code documents to RAG system
        
        Args:
            parsed_data: Dictionary of parsed code files
        """
        logger.info(f" Adding {len(parsed_data)} code documents to RAG system")
        
        added_count = 0
        updated_count = 0
        
        for filename, data in parsed_data.items():
            doc_id = self._generate_doc_id(filename, data['code'])
            
            # Check if document already exists
            is_update = doc_id in self.code_documents
            
            # Store document
            self.code_documents[doc_id] = {
                'filename': filename,
                'code': data['code'],
                'language': data.get('language', 'unknown'),
                'functions': data.get('functions', []),
                'classes': data.get('classes', []),
                'imports': data.get('imports', []),
                'complexity': data.get('complexity', 'medium'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Create simple embeddings (keyword-based)
            self.embeddings[doc_id] = self._create_simple_embedding(data)
            
            # Store metadata
            self.metadata[doc_id] = {
                'filename': filename,
                'language': data.get('language', 'unknown'),
                'num_functions': len(data.get('functions', [])),
                'num_classes': len(data.get('classes', [])),
                'loc': data.get('lines_of_code', 0)
            }
            
            if is_update:
                updated_count += 1
                logger.debug(f"  Updated: {filename}")
            else:
                added_count += 1
                logger.debug(f"  Added: {filename}")
        
        logger.info(f" RAG update complete: {added_count} added, {updated_count} updated")
        
        # Persist to disk
        self._save_storage()
    
    def get_relevant_context(
        self,
        query: str,
        max_results: int = 3
    ) -> str:
        """
        Get relevant code context for a query
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            Formatted context string
        """
        logger.debug(f" Searching for context: '{query[:50]}...'")
        
        if not self.code_documents:
            logger.warning(" No code documents available in RAG system")
            return "No code context available."
        
        # Simple keyword matching
        query_keywords = self._extract_keywords(query.lower())
        logger.debug(f"   Keywords extracted: {list(query_keywords.keys())[:5]}")
        
        # Score documents
        scores = {}
        for doc_id, embedding in self.embeddings.items():
            score = self._calculate_similarity(query_keywords, embedding)
            scores[doc_id] = score
        
        # Get top results
        sorted_docs = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:max_results]
        
        logger.debug(f"   Top scores: {[f'{doc[:8]}:{score:.2f}' for doc, score in sorted_docs[:3]]}")
        
        # Format context
        context_parts = []
        relevant_count = 0
        
        for doc_id, score in sorted_docs:
            if score > 0:
                doc = self.code_documents[doc_id]
                context_parts.append(
                    f"File: {doc['filename']}\n"
                    f"Language: {doc['language']}\n"
                    f"Functions: {', '.join([f['name'] for f in doc['functions'][:5]])}\n"
                    f"Classes: {', '.join([c['name'] for c in doc['classes'][:3]])}\n"
                    f"Code snippet:\n{doc['code'][:500]}...\n"
                )
                relevant_count += 1
        
        if relevant_count > 0:
            logger.info(f" Found {relevant_count} relevant documents")
        else:
            logger.warning(" No relevant context found")
        
        return "\n---\n".join(context_parts) if context_parts else "No relevant context found."
    
    def get_code_versions(self, filename: str) -> List[Dict]:
        """Get all versions of a specific file"""
        logger.debug(f" Retrieving versions for: {filename}")
        
        versions = []
        
        for doc_id, doc in self.code_documents.items():
            if doc['filename'] == filename:
                versions.append(doc)
        
        versions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        logger.debug(f"   Found {len(versions)} version(s)")
        
        return versions
    
    def search_by_function(self, function_name: str) -> List[Dict]:
        """Search for documents containing a specific function"""
        logger.debug(f" Searching for function: {function_name}")
        
        results = []
        
        for doc_id, doc in self.code_documents.items():
            for func in doc['functions']:
                if function_name.lower() in func['name'].lower():
                    results.append({
                        'doc_id': doc_id,
                        'filename': doc['filename'],
                        'function': func
                    })
        
        logger.debug(f"   Found {len(results)} match(es)")
        
        return results
    
    def search_by_class(self, class_name: str) -> List[Dict]:
        """Search for documents containing a specific class"""
        logger.debug(f" Searching for class: {class_name}")
        
        results = []
        
        for doc_id, doc in self.code_documents.items():
            for cls in doc['classes']:
                if class_name.lower() in cls['name'].lower():
                    results.append({
                        'doc_id': doc_id,
                        'filename': doc['filename'],
                        'class': cls
                    })
        
        logger.debug(f"   Found {len(results)} match(es)")
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get RAG system statistics"""
        total_functions = sum(
            len(doc['functions'])
            for doc in self.code_documents.values()
        )
        
        total_classes = sum(
            len(doc['classes'])
            for doc in self.code_documents.values()
        )
        
        languages = set(
            doc['language']
            for doc in self.code_documents.values()
        )
        
        stats = {
            'total_documents': len(self.code_documents),
            'total_functions': total_functions,
            'total_classes': total_classes,
            'languages': list(languages),
            'storage_size': len(json.dumps(self.code_documents))
        }
        
        logger.debug(f" RAG Statistics: {stats['total_documents']} docs, "
                    f"{stats['total_functions']} functions, "
                    f"{stats['total_classes']} classes")
        
        return stats
    
    def _generate_doc_id(self, filename: str, code: str) -> str:
        """Generate unique document ID"""
        content = f"{filename}:{code}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _create_simple_embedding(self, data: Dict) -> Dict[str, int]:
        """Create simple keyword-based embedding"""
        keywords = {}
        
        # Extract keywords from filename
        filename_words = data['filename'].replace('.', ' ').replace('_', ' ').split()
        for word in filename_words:
            keywords[word.lower()] = keywords.get(word.lower(), 0) + 2
        
        # Extract from function names
        for func in data.get('functions', []):
            name_parts = func['name'].replace('_', ' ').split()
            for part in name_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 3
        
        # Extract from class names
        for cls in data.get('classes', []):
            name_parts = cls['name'].replace('_', ' ').split()
            for part in name_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 3
        
        # Extract from imports
        for imp in data.get('imports', []):
            imp_parts = imp.replace('.', ' ').split()
            for part in imp_parts:
                keywords[part.lower()] = keywords.get(part.lower(), 0) + 1
        
        # Add language
        keywords[data.get('language', 'unknown').lower()] = 5
        
        return keywords
    
    def _extract_keywords(self, text: str) -> Dict[str, int]:
        """Extract keywords from text"""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was',
            'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'test', 'tests', 'testing', 'generate', 'create'
        }
        
        words = text.lower().split()
        keywords = {}
        
        for word in words:
            word = ''.join(c for c in word if c.isalnum() or c == '_')
            
            if word and word not in stop_words and len(word) > 2:
                keywords[word] = keywords.get(word, 0) + 1
        
        return keywords
    
    def _calculate_similarity(
        self,
        query_keywords: Dict[str, int],
        doc_embedding: Dict[str, int]
    ) -> float:
        """Calculate simple similarity score"""
        score = 0.0
        
        for keyword, query_weight in query_keywords.items():
            if keyword in doc_embedding:
                score += query_weight * doc_embedding[keyword]
        
        return score
    
    def _save_storage(self):
        """Save RAG data to disk"""
        storage_file = self.storage_dir / "rag_data.json"
        
        try:
            data = {
                'code_documents': self.code_documents,
                'embeddings': self.embeddings,
                'metadata': self.metadata,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            file_size = storage_file.stat().st_size / 1024
            logger.debug(f" RAG data saved ({file_size:.2f} KB)")
            
        except Exception as e:
            logger.error(f" Error saving RAG storage: {e}", exc_info=True)
    
    def _load_storage(self):
        """Load RAG data from disk"""
        storage_file = self.storage_dir / "rag_data.json"
        
        if storage_file.exists():
            try:
                with open(storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.code_documents = data.get('code_documents', {})
                self.embeddings = data.get('embeddings', {})
                self.metadata = data.get('metadata', {})
                
                last_updated = data.get('last_updated', 'unknown')
                logger.info(f" Loaded existing RAG data (last updated: {last_updated})")
                logger.info(f"   Documents: {len(self.code_documents)}")
                
            except Exception as e:
                logger.error(f" Error loading RAG storage: {e}")
                logger.info("   Starting with fresh storage")
        else:
            logger.info("No existing RAG data found, starting fresh")
    
    def clear_storage(self):
        """Clear all stored data"""
        logger.info(" Clearing all RAG storage")
        
        self.code_documents = {}
        self.embeddings = {}
        self.metadata = {}
        self._save_storage()
        
        logger.info(" RAG storage cleared")