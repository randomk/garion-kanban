# 🧠 Garion Kanban

> Kanban board live conectado ao Clawdbot

## ✨ Features

- **📋 Kanban Board** — TODO, DOING, DONE
- **⚡ Realtime** — WebSocket para atualizações live
- **🖱️ Drag & Drop** — Mova tasks entre colunas
- **🧠 Clawdbot Integration** — Crie tasks via chat
- **📱 Responsivo** — Funciona em mobile

## 🔌 API para Clawdbot

```bash
# Listar tasks
GET /api/tasks

# Criar task
POST /api/tasks
{"title": "Fazer algo", "description": "Detalhes", "priority": "high", "source": "clawdbot"}

# Atualizar task
PATCH /api/tasks/<id>
{"status": "done"}

# Deletar task
DELETE /api/tasks/<id>
```

## 🚀 Deploy

```bash
railway up
```

## 👤 Criado por

**Garion** 🧠 para **Rodrigo Melgar**
CTO @ Swap

---

*"Task criada é task que vai ser feita."*
