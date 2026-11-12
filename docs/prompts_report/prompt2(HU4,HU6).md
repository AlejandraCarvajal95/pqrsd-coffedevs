Escribí los tres archivos en data/conocimiento/. Git no los ignora y quedan sin seguimiento. No hice commit. Según CLAUDE.md, les corresponde una rama feat/... para US-004 y un PR revisado.

*   [**politica\_y\_contratos.md**](vscode-webview://0u17hstdmn5dsigg1ohhhr4pvhujgjctkerc4bker05n96om2ika/data/conocimiento/politica_y_contratos.md)**:** describe Banco Andino Ficticio y sus cuatro áreas (Tarjetas de Crédito, Cartera, Seguros de Vida y Jurídica). Incluye la política de atención de PQRSD y un extracto de nueve cláusulas de la "Tarjeta de Crédito Andina Clásica".
    
    *   Los teléfonos, correos y cifras son ficticios, y los correos usan el dominio .example.
        
    *   Los umbrales del semáforo (50 % y 20 %) y el criterio de conteo vienen de docs/arquitectura.md y docs/backlog.md.
        
*   [**faq\_clientes.md**](vscode-webview://0u17hstdmn5dsigg1ohhhr4pvhujgjctkerc4bker05n96om2ika/data/conocimiento/faq_clientes.md)**:** cinco preguntas sobre cuota de manejo, cancelación de la tarjeta, reporte en centrales de riesgo, compras no reconocidas y cancelación del seguro de vida. Cada respuesta cita la cláusula del contrato en que se apoya.
    
*   [**normativa\_ley\_1755.md**](vscode-webview://0u17hstdmn5dsigg1ohhhr4pvhujgjctkerc4bker05n96om2ika/data/conocimiento/normativa_ley_1755.md)**:** tiene una tabla de plazos con una clave por tipo (queja, reclamo, peticion\_informacion…), pensada para pasarla a la configuración del motor de plazos.
    
    *   También incluye las reglas de conteo, los festivos de nov-dic 2026 y las prórrogas y casos especiales.
        
    *   Trae dos ejemplos de cálculo de vencimiento que revisé a mano. Una queja radicada el 3 nov 2026 vence el 25 nov, por el festivo del 16 nov. Una petición de información vence el 18 nov.
        

Cada archivo está dividido por secciones ##, así cargar\_conocimiento.py puede cortar por sección y conservar el documento y la sección para las citas (US-005).

**Plazos:** los sé de memoria, así que el equipo debe confirmarlos contra el texto oficial antes de la entrega, como pide US-004.

*   **Art. 14:** 15 días para la regla general, 10 para documentos o información, 30 para consultas, y prórroga hasta el doble.
    
*   **Otros artículos:** el traslado por incompetencia en 5 días (art. 21) y el desistimiento tácito al mes (art. 17).
    
*   **Ley 1266/2008 y 2157/2021:** el resumen menciona la comunicación previa al reporte negativo y no da cifras. Los plazos de esas leyes para reclamos de datos y la permanencia del dato negativo no los incluí, y conviene verificarlos antes de agregarlos.
    
*   **Festivos:** los de noviembre y diciembre de 2026 los deduje del calendario, así que también conviene confirmarlos.
    

**Sugerencias y denuncias:** la ley no les fija un plazo propio. El documento les aplica 15 días hábiles como criterio interno del Banco y lo dice expresamente. Si el equipo prefiere otro criterio, es el único lugar que hay que cambiar.