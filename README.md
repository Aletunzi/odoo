# Odoo Tutorial Agent

Agente Q&A con interfaccia web sui tutorial ufficiali Odoo.  
Ogni push al repository fa partire un nuovo deploy in automatico su Render.

---

## Setup iniziale su Render (una volta sola, solo clic)

1. Vai su [dashboard.render.com](https://dashboard.render.com)
2. **New** → **Web Service**
3. Connetti il repository GitHub → seleziona questo repo
4. Render rileva automaticamente il file `render.yaml` — non cambiare nulla
5. Clicca **Create Web Service**
6. Nel pannello del servizio → **Environment** → aggiungi la variabile:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   ```
7. Clicca **Save Changes** → il deploy riparte con la chiave

**Da quel momento: ogni push = deploy automatico.**

---

## Cosa succede ad ogni deploy

```
Push su GitHub
  └── Render costruisce l'immagine Docker
        └── entrypoint.sh gira in automatico:
              ├── [solo primo avvio] Scraping video da Odoo
              ├── [solo primo avvio] Download trascrizioni YouTube  
              ├── [solo primo avvio] Costruzione indice ChromaDB
              └── Server online → https://odoo-agent.onrender.com
```

Trascrizioni e indice sono salvati nel volume `/app/data` e **non vengono rigenerati** ai deploy successivi.

> **Nota**: il primo avvio impiega 10–30 minuti. Render aspetta il segnale `/api/status` prima di dichiarare il servizio online.

---

## Piano Render consigliato

| Piano | RAM | Disco | Adatto |
|-------|-----|-------|--------|
| Free | 512MB | ✗ | No — RAM insufficiente per il modello di embedding |
| Starter ($7/mese) | 512MB | ✗ | No — stesso problema |
| Standard ($25/mese) | 2GB | ✓ | **Sì** — RAM sufficiente + disco persistente |

Il modello di embedding (`paraphrase-multilingual-MiniLM-L12-v2`) richiede circa 1GB di RAM.
