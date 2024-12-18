# 📖 **Narrator**

**Narrator** is a streamlined application for processing EPUB files into clean text, preparing them for TTS (Text-to-Speech) generation.

---

## 🚀 **Routes Overview**

### 1. **Epoub Upload**
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

### 3. **Cleaned Text**
- **Path:** `/cleaned`  
- **Purpose:**  
  Displays a list of all cleaned text files, ready for TTS generation.  
  - Provides a viewer-friendly table of available files.  

---

### 4. **Archived Text**
- **Path:** `/text-archive`  
- **Purpose:**  
  Displays a list of all cleaned text files that have had tts executed against it.  
  - Provides a viewer-friendly table of available files.  

---

### 5. **Final Audio**
- **Path:** `/audio`  
- **Purpose:**  
  Displays a list of the final tts products.  
  - Provides a viewer-friendly table of available files. 
  - Provides a button to download the wav from the container to local machine 

---

### 6. **Queued TTS**
- **Path:** `/current-queue`
- **Purpose:**  
  Provides a list of things that hve been added to the tts queue.  
  - Provides a list of everything in the processing queue. 

---

### 7. **Add Overlay**
- **Path:** `/upload-overlay`
- **Purpose:**  
  Provides a way of adding music to the overlay lib. 

---

