# Manual de ensamble personalizado

## Resumen de compatibilidad
- **Estado:** Compatible
- **Consumo estimado:** 390 W
- **Fuente recomendada:** 540 W (elegida: 750 W)

## Tus piezas

| Pieza | Modelo |
|---|---|
| Procesador | AMD Ryzen 5 7600X 4.7 GHz 6-Core Processor (100-100000593WOF) |
| Placa madre | Asus TUF GAMING B650-PLUS WIFI ATX AM5 Motherboard (TUF GAMING B650-PLUS WIFI) |
| Tarjeta gráfica | Asus TUF GAMING GeForce RTX 4070 12 GB Video Card (tuf-rtx4070-12g-gaming) |
| Memoria RAM | Corsair Vengeance 32 GB (2 x 16 GB) DDR5-6000 CL36 Memory (CMK32GX5M2D6000C36) |
| Almacenamiento | Samsung 980 Pro 1 TB M.2-2280 PCIe 4.0 X4 NVME Solid State Drive (MZ-V8P1T0B/AM) |
| Refrigeración | Cooler Master Hyper 212 Black Edition 42 CFM CPU Cooler (RR-212S-20PK-R2) |
| Fuente de poder | Corsair RM750e (2023) 750 W 80+ Gold Certified Fully Modular ATX Power Supply (CP-9020262-NA) |
| Gabinete | Corsair 4000D Airflow ATX Mid Tower Case (CC-9011200-WW) |

## Pasos de ensamble

### 1. Preparar el área de trabajo

Sin manual disponible para esta pieza. Desconectar el equipo de la red eléctrica y preparar una superficie segura.

### 2. Instalar el procesador

- Desconecte todos los cables de alimentación antes de instalar el procesador [Manual ASUS B650, pág. 1-10].  
- Verifique que el procesador sea compatible con el socket AM5, ya que tiene un diseño de pines diferente [Manual ASUS B650, pág. 1-10].  
- El procesador solo encaja en una orientación correcta; no lo fuerce para evitar dañar los contactos del socket y el propio CPU [Manual ASUS B650, pág. 1-10].

### 3. Instalar la memoria RAM

- Instale los dos módulos DDR5 en las ranuras DIMM correspondientes a la configuración de doble canal recomendada por el manual de la placa base [Manual ASUS B650, pág. 1-12].  
- La placa dispone de cuatro ranuras DDR5 organizadas en dos canales: Canal A (DIMM_A1 y DIMM_A2) y Canal B (DIMM_B1 y DIMM_B2) [Manual ASUS B650, pág. 1-12].  
- Asegúrese de que ambos módulos tengan la misma latencia CAS y, de ser posible, el mismo código de fecha y proveedor para una compatibilidad óptima [Manual ASUS B650, pág. 1-12].  
- Inserte cada módulo alineando la muesca con la ranura y presione firmemente hasta que los pestillos laterales se enganchen automáticamente [Manual ASUS B650, pág. 1-3].

### 4. Instalar la unidad NVMe

Montar la unidad M.2 en la placa antes de introducirla en el gabinete.

_No se pudo verificar el detalle del manual para este paso._

### 5. Aplicar pasta térmica

Sin manual disponible para esta pieza. Verificar si el disipador trae pasta preaplicada; si no, colocarla siguiendo las instrucciones del fabricante.

### 6. Instalar disipador por aire

- Conecte el ventilador del disipador al conector **CPU_FAN** de la placa base (1 A, 12 W, control Q‑Fan) [Manual ASUS B650, pág. 1-3].  
- Verifique que la placa esté orientada con el lado indicado hacia la parte trasera del chasis antes de fijar el disipador [Manual ASUS B650, pág. 1-2].  
- Asegure el disipador al socket AM5 siguiendo el mecanismo de montaje del cooler (tornillos/clip) sin forzar los módulos DDR5 adyacentes.  
- Si el disipador incluye un segundo ventilador, puede usar el conector **CPU_OPT** (mismas especificaciones que CPU_FAN) [Manual ASUS

### 7. Preparar el gabinete

Sin manual disponible para esta pieza. Abrir el gabinete, comprobar separadores y preparar el espacio para la placa.

### 8. Instalar la fuente de poder

Sin manual disponible para esta pieza. Fijar la fuente en el gabinete, con el cable de corriente desconectado.

### 9. Montar la placa madre

- Antes de manipular la placa, desconecta el cable de alimentación y usa una pulsera antiestática o toca un objeto metálico conectado a tierra para evitar daños por electricidad estática [Manual ASUS B650, pág. 1-1].  
- Orienta la placa madre de modo que el lado indicado en el diagrama quede hacia la parte trasera del chasis [Manual ASUS B650, pág. 1-2].  
- Alinea los orificios de la placa con los separadores (standoffs) del gabinete y atornilla sin forzar los tornillos para fijarla firmemente.

### 10. Conectar alimentación de la placa

- Antes de manipular cables, desconecta el cable de alimentación de la pared y asegúrate de que la fuente esté apagada [Manual ASUS B650, pág. 1-1].  
- Conecta el conector principal ATX y el conector de 8 pines CPU/EPS (o ambos de 8 y 4 pines si tu placa lo requiere) en la orientación correcta, ya que solo encajan de una forma [Manual ASUS B650, pág. 1-3].  
- Empuja firmemente cada conector hasta que quede completamente insertado y asegurado [Manual ASUS B650, pág. 1-3].

### 11. Conectar panel frontal

- Conecte el LED de encendido del sistema (PLED) al encabezado de 2 o 3-1 pines indicado en el manual [Manual ASUS B650, pág. 1-6].  
- Conecte el LED de actividad de almacenamiento (HDD_LED) al encabezado de 2 pines correspondiente [Manual ASUS B650, pág. 1-6].  
- Conecte el altavoz de advertencia del chasis (SPEAKER) al encabezado de 4 pines [Manual ASUS B650, pág. 1-6].  
- Conecte el botón de encendido/apagado suave (PWRSW) al encabezado de 3-1 pines [Manual ASUS B650, pág. 1-6].  
- Conecte el botón de reinicio (RESET) al encabezado de 2 pines y, si aplica, el sensor de intrusión del chasis (CHASSIS) a su encabezado de 2 pines [Manual ASUS B650, pág. 1-6].

### 12. Instalar la tarjeta gráfica

- Inserte la tarjeta gráfica en una de las ranuras PCIe x16 de la placa base (PCIEX16_1 o PCIEX16_2) [Manual ASUS B650, pág. 1-2].
- La placa base soporta hasta dos tarjetas gráficas PCIe x16 según la sección de ranuras de expansión [Manual ASUS B650, pág. 1-3].
- Fije el soporte metálico de la tarjeta al chasis del gabinete Corsair 4000D Airflow mediante el tornillo correspondiente.

### 13. Conectar alimentación de la GPU

Sin manual disponible para esta pieza. Conectar los cables PCIe/12VHPWR requeridos por la tarjeta gráfica, si aplica.

### 14. Revisar conexiones

- Verifica que los conectores de alimentación ATX (8 pines y 4 pines) estén completamente insertados y bien orientados [Manual ASUS B650, pág. 1-3].  
- Comprueba que todos los ventiladores (CPU_FAN, CPU_OPT, AIO_PUMP, CHA_FAN1‑4) tengan sus cables conectados a los headers correspondientes [Manual ASUS B650, pág. 1-2].  
- Asegúrate de que los conectores frontales (PANEL, AAFP), SATA, PCIe y de audio estén firm

### 15. Cerrar el gabinete

Sin manual disponible para esta pieza. Organizar los cables y volver a colocar los paneles del gabinete.