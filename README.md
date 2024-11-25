# 📖 **Narrator**

**Narrator** is a streamlined application for processing EPUB files into clean text, preparing them for TTS (Text-to-Speech) generation.

---

## 🚀 **Routes Overview**

### 1. **Upload**
- **Path:** `/upload`  
- **Purpose:**  
  Allows users to upload an EPUB file to be processed.  
  Users can also provide:
  - **Author**: For adding metadata.  
  - **Title**: For customizing episode introductions.  

---

### 2. **Process**
- **Path:** `/process`  
- **Purpose:**  
  Automatically triggered upon submitting an upload.  
  - Conducts cleaning and extraction of text from the uploaded EPUB file.  
  - Prepares the content for further TTS processing.

---

### 3. **Cleaned**
- **Path:** `/cleaned`  
- **Purpose:**  
  Displays a list of all cleaned text files, ready for TTS generation.  
  - Provides a viewer-friendly table of available files.  
  - Includes a button placeholder for future functionality.

---

