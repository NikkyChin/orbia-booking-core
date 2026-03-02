from django.db import models

# V1: no necesitamos modelos.
# El estado conversacional vive en apps.clientes.Conversacion
# y los mensajes se manejan por webhooks + services.