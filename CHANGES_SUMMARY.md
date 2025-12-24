# Pipeline Changes Summary - Supervisor Requirements

## Date: 2025-12-23
## Changes Requested by Supervisor

### 🎯 Main Changes

1. **Cluster CLASSES instead of METHODS**
   - Old: Clustered individual methods
   - New: Clusters entire classes semantically

2. **Enhanced Class Summaries with Method Call Analysis**
   - Old: Basic class summaries
   - New: Analyzes what methods each class calls to create more specific summaries
   - Improves semantic understanding of class functionality

---

## 📝 Detailed Changes

### 1. New File: `src/clustering/codebert_clustering.py`
**Added:** `CodeBERTClassClustering` class
- Clusters classes using CodeBERT embeddings
- Uses K-Means clustering with optimal k selection (Silhouette score)
- Groups semantically similar classes together

### 2. Updated: `src/clustering/clustering.py`
**Added:** `cluster_classes_semantically()` function
- Extracts all classes from parsed files
- Uses CodeBERT to embed entire class code
- Finds optimal number of clusters (k=2 to k=15)
- Returns class clusters instead of method clusters

**Kept:** `cluster_methods_semantically()` for backward compatibility

### 3. New File: `src/summarizing/enhanced_summarizer.py`
**Created:** `EnhancedLlamaSummarizer` class

**Key Features:**
- `extract_method_calls()` - Analyzes which methods a class calls
- `extract_class_dependencies()` - Identifies classes used
- `summarize_class_with_context()` - Creates context-aware class summaries
- `summarize_cluster()` - Summarizes groups of related classes

**Improvements:**
- Understands what a class DOES by analyzing its method calls
- More specific summaries that capture class purpose
- Better semantic context for vulnerability detection

### 4. Updated: `main.py`
**Changes:**
- Imports `cluster_classes_semantically` instead of `cluster_methods_semantically`
- Imports `EnhancedLlamaSummarizer` instead of `LlamaSummarizer`
- Renamed `cluster_methods()` → `cluster_classes()`
- Updated `generate_summaries()` to use enhanced summarizer
- Updated `save_outputs()` to save class clusters

**Cluster JSON Format (NEW):**
```json
{
  "cluster_id": 1,
  "size": 3,
  "classes": [
    {
      "name": "BankLogin",
      "file": "/path/to/BankLogin.java",
      "num_methods": 5
    }
  ]
}
```

**Old Format (for reference):**
```json
{
  "cluster_id": 1,
  "size": 10,
  "methods": [
    {
      "name": "login",
      "class": "BankLogin",
      "file": "/path/to/BankLogin.java"
    }
  ]
}
```

### 5. Updated: `src/generate_results.py`
**Changes:**
- Maps classes to clusters (instead of methods to clusters)
- Looks up cluster via parent class name
- Backward compatible with old method-based format

---

## 🔄 How It Works Now

### Pipeline Flow:

```
1. Scan with MobSF → vulnerabilities.json

2. Parse Java files → classes & methods

3. Cluster CLASSES semantically
   - Group similar classes together
   - Each cluster represents related functionality

4. Analyze vulnerabilities → map to methods

5. Generate Enhanced Summaries:
   a) Method summaries (what the method does)
   b) Class summaries WITH METHOD CALL ANALYSIS
      - What methods it calls
      - What classes it uses
      - More specific, context-aware
   c) Cluster summaries (what group of classes does)

6. Generate results.json
   - Each vulnerability has 3 levels of context
   - Cluster info is based on parent class
```

### Example: Enhanced Class Summary

**Old Summary (basic):**
> "This class handles user authentication."

**New Summary (with method call analysis):**
> "This class handles user authentication by calling validateCredentials(), hashPassword(), and storeSession(); uses UserDatabase and SessionManager classes; defines login(), logout(), and refreshToken() methods."

**Benefits:**
- More specific understanding of class purpose
- Better context for vulnerability assessment
- Improved false positive detection

---

## 🚀 How to Run

### Full Pipeline (with changes):
```bash
cd /Users/panagiotisbinikos/Desktop/CB_Thesis/code/LLM-Pipeline

python main.py --dir data/apps/DamnVulnerableBank --scan
```

### Generate Results Only (from existing outputs):
```bash
python generate_results_standalone.py --output-dir out_Damn-Vulnerable-Bank/
```

---

## 📊 Expected Output Structure

### clusters.json (NEW):
```json
[
  {
    "cluster_id": 1,
    "size": 3,
    "classes": [
      {"name": "BankLogin", "file": "...", "num_methods": 5},
      {"name": "AuthHandler", "file": "...", "num_methods": 7},
      {"name": "SessionManager", "file": "...", "num_methods": 4}
    ]
  }
]
```

### summaries.json (ENHANCED):
```json
{
  "clusters": {
    "cluster_1": "Authentication and session management classes that handle login, validation, and token management"
  },
  "classes": {
    "BankLogin": "Handles user authentication by validating credentials and managing sessions; calls validateUser(), createSession(), and uses AuthDatabase"
  },
  "methods": {
    "BankLogin.login": "Authenticates user with provided credentials and creates session"
  }
}
```

### results.json:
```json
{
  "results": [
    {
      "file": "/path/to/BankLogin.java",
      "line": 86,
      "method": "BankLogin.bankLogin",
      "vulnerability": "android_logging",
      "match": "Log.d(TAG, accessToken)",
      "summaries": {
        "method": "...",
        "class": "... [with method call analysis]",
        "cluster": "... [what the cluster of related classes does]"
      }
    }
  ]
}
```

---

## 🔬 Key Improvements for Research

### 1. Better Semantic Understanding
- Classes are the natural unit of functionality
- Clustering classes groups related features
- More meaningful semantic context

### 2. Enhanced False Positive Detection
- Method call analysis provides deeper context
- Understanding what a class USES helps identify intent
- Cluster summaries show broader architectural context

### 3. More Specific Summaries
- "This class authenticates users" → Too vague
- "This class authenticates users by calling validateCredentials() and hashPassword(), using UserDatabase" → Much more specific

### 4. Better for LLM Analysis
- 3 levels of context (method, class, cluster)
- Class-level context is more informative than method-level
- Helps LLMs make better judgments about vulnerabilities

---

## 🧪 Testing

To test the changes:

```bash
# 1. Test on existing data (should generate results.json)
python generate_results_standalone.py --output-dir out_Damn-Vulnerable-Bank/

# 2. Run full pipeline on a test app
python main.py --dir data/apps/DamnVulnerableBank --scan

# 3. Check outputs
ls out/clusters.json    # Should show class clusters
ls out/summaries.json   # Should have enhanced summaries
ls out/results.json     # Should have vulnerability results
```

---

## 📌 Backward Compatibility

The `generate_results.py` handles both formats:
- New format: `clusters.json` with "classes" field
- Old format: `clusters.json` with "methods" field

This ensures existing data still works while new data uses improved structure.

---

## ✅ Summary

**Changes Implemented:**
1. ✅ Cluster classes instead of methods
2. ✅ Analyze method calls within classes for better summaries
3. ✅ Enhanced LLM prompts with contextual information
4. ✅ Updated pipeline to use new clustering and summarization
5. ✅ Updated results generation to work with class clusters
6. ✅ Backward compatibility maintained

**Research Impact:**
- More meaningful semantic clustering
- Better context for vulnerability analysis
- Improved false positive detection potential
- Aligned with supervisor's requirements

---

## 📧 Questions?

If you need any adjustments or have questions about the implementation, the changes are modular and can be easily modified.
