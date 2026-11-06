"""Kratos Sovereign Multi-Engine Database Catalog & Non-Technical Documentation.

Primary references from Kaggle datasets, business explanations, general ERDs (Mermaid),
and natural language query examples for non-technical executives and data teams.
"""

from __future__ import annotations
from typing import Any

DATABASE_CATALOG: dict[str, dict[str, Any]] = {
    "northwind": {
        "id": "northwind",
        "title": "Northwind Traders",
        "subtitle": "Comercio Internacional de Alimentos Gourmet & Logística B2B",
        "emoji": "🚢",
        "kaggle_source": {
            "name": "Microsoft Northwind SQLite Database",
            "url": "https://www.kaggle.com/datasets/rajatsurana99/northwind-database-sqlite",
            "author": "Microsoft Corporation (Port SQLite por Kaggle Community)",
            "license": "Public Domain / Open Educational",
            "scope": "11 tablas relacionales, transacciones históricas de exportación/importación"
        },
        "non_technical_summary": (
            "Imagina que eres el director general de una empresa internacional de importación y exportación "
            "llamada 'Northwind Traders'. Tu empresa compra alimentos gourmet exóticos a productores artesanales "
            "de todo el mundo (quesos de Francia, mermeladas de Escocia, vinos de Italia, carnes nórdicas) y los "
            "vende al por mayor a restaurantes, hoteles y tiendas de delicatessen en más de 20 países.\n\n"
            "Esta base de datos es la bitácora operativa de la compañía: registra cada llamada de ventas, qué vendedor "
            "cerró el trato, qué descuento especial se acordó, en qué barco o camión de carga se transportaron las cajas, "
            "cuántos días tardó el flete en llegar a destino y qué productos están a punto de agotarse en el almacén."
        ),
        "business_value": (
            "Permite a gerentes comerciales y analistas financieros evaluar qué productos generan más margen neto, "
            "qué representantes de ventas superan sus cuotas, qué países son más rentables y qué proveedores son confiables "
            "en sus tiempos de entrega."
        ),
        "modules": [
            {
                "name": "Ventas y Pedidos",
                "tables": ["orders", "order_details"],
                "description": "Cabecera y detalle de las transacciones comerciales: fechas de solicitud y despacho, transportista, precios unitarios cobrados, cantidades vendidas y descuentos aplicados."
            },
            {
                "name": "Catálogo e Inventario",
                "tables": ["products", "categories", "suppliers"],
                "description": "Catálogo completo de SKUs agrupados por familias (Bebidas, Lácteos, Carnes, etc.), precios de lista, unidades disponibles en almacén y proveedores que los abastecen."
            },
            {
                "name": "Clientes y Geografía",
                "tables": ["customers", "regions", "territories"],
                "description": "Empresas compradoras distribuidas por países, ciudades y territorios comerciales asignados."
            },
            {
                "name": "Fuerza de Ventas y Logística",
                "tables": ["employees", "employee_territories", "shippers"],
                "description": "Agentes comerciales, jerarquía interna de reporte a gerencia y transportistas navieros responsables del flete."
            }
        ],
        "tables_detail": [
            {"table": "categories", "desc": "Familias comerciales de productos (Bebidas, Condimentos, Lácteos, etc.)."},
            {"table": "suppliers", "desc": "Proveedores globales de materias primas y alimentos elaborados."},
            {"table": "customers", "desc": "Clientes corporativos, compradores mayoristas y su ubicación en más de 20 países."},
            {"table": "products", "desc": "Artículos del catálogo con precio unitario, stock disponible y estado de descontinuado."},
            {"table": "orders", "desc": "Órdenes de compra emitidas, con fecha de pedido, fecha de entrega y flete pagado."},
            {"table": "order_details", "desc": "Líneas de pedido con precio real pactado, cantidad comprada y porcentaje de descuento."},
            {"table": "employees", "desc": "Equipo comercial con nombres, cargos, fecha de contratación y supervisor a quien reportan."},
            {"table": "shippers", "desc": "Empresas de transporte marítimo y terrestre (Speedy Express, United Package, Federal Shipping)."},
            {"table": "territories", "desc": "Zonas geográficas de venta asignadas a los agentes comerciales."},
            {"table": "employee_territories", "desc": "Mapeo que asigna qué vendedor tiene a cargo qué territorio específico."},
            {"table": "regions", "desc": "Macro-regiones comerciales (Norte, Sur, Este, Oeste)."}
        ],
        "mermaid_erd": """erDiagram
    CATEGORIES ||--|{ PRODUCTS : "clasifica"
    SUPPLIERS ||--|{ PRODUCTS : "suministra"
    PRODUCTS ||--|{ ORDER_DETAILS : "incluido_en"
    ORDERS ||--|{ ORDER_DETAILS : "contiene"
    CUSTOMERS ||--|{ ORDERS : "solicita"
    EMPLOYEES ||--|{ ORDERS : "gestiona"
    SHIPPERS ||--|{ ORDERS : "transporta"
    REGIONS ||--|{ TERRITORIES : "agrupa"
    TERRITORIES ||--|{ EMPLOYEE_TERRITORIES : "asignado_a"
    EMPLOYEES ||--|{ EMPLOYEE_TERRITORIES : "atiende"
    EMPLOYEES ||--o{ EMPLOYEES : "reporta_a"

    CATEGORIES {
        int categoryID PK
        string categoryName
        string description
    }
    PRODUCTS {
        int productID PK
        string productName
        int supplierID FK
        int categoryID FK
        float unitPrice
        int unitsInStock
    }
    ORDERS {
        int orderID PK
        string customerID FK
        int employeeID FK
        datetime orderDate
        datetime shippedDate
        float freight
        string shipCountry
        string shipRegion
        string shipCity
    }
    ORDER_DETAILS {
        int orderID PK,FK
        int productID PK,FK
        float unitPrice
        int quantity
        float discount
    }
    CUSTOMERS {
        string customerID PK
        string companyName
        string contactName
        string country
        string region
        string city
        string postalCode
    }
    EMPLOYEES {
        int employeeID PK
        string firstName
        string lastName
        string title
        int reportsTo FK
    }
    SHIPPERS {
        int shipperID PK
        string companyName
    }
    SUPPLIERS {
        int supplierID PK
        string companyName
        string country
    }""",
        "erd_explanation": (
            "1. Un Cliente (CUSTOMERS) emite una o varias Órdenes (ORDERS).\n"
            "2. Cada Orden es atendida por un Empleado (EMPLOYEES) y enviada a través de un Transportista (SHIPPERS).\n"
            "3. La Orden contiene múltiples renglones en Detalle de Orden (ORDER_DETAILS), donde se vincula cada Producto (PRODUCTS).\n"
            "4. Cada Producto pertenece a una Categoría (CATEGORIES) y proviene de un Proveedor (SUPPLIERS)."
        ),
        "example_queries": [
            {
                "query": "dame las 5 categorías con mayor facturación histórica",
                "pattern": "Ranking Top N (Pareto)",
                "insight": "Descubre qué líneas de negocio generan el mayor porcentaje de los ingresos brutos de la compañía."
            },
            {
                "query": "escoge las 3 categorías que peor desempeño tienen en el tiempo luego muestrame el comportamiento de las ventas diarias de esas categorías a través del tiempo",
                "pattern": "Multi-Series Time Series con Cohorte",
                "insight": "Diagnostica la cohorte de productos rezagados para analizar volatilidad y caídas críticas de demanda."
            },
            {
                "query": "top 3 empleados con mayor volumen de ventas en dólares",
                "pattern": "Ranking de Desempeño Comercial",
                "insight": "Premia a los mejores cerradores de acuerdos y balancea la carga de la fuerza comercial."
            },
            {
                "query": "cuáles son los 5 productos más vendidos y cuántas unidades tienen en stock",
                "pattern": "Diagnóstico de Inventario & Quiebre de Stock",
                "insight": "Identifica artículos de alta rotación en riesgo de desabastecimiento inmediato."
            },
            {
                "query": "top 5 países con mayor volumen de pedidos",
                "pattern": "Distribución Geográfica",
                "insight": "Planifica rutas marítimas y convenios arancelarios con base en la concentración territorial."
            }
        ]
    },

    "chinook": {
        "id": "chinook",
        "title": "Chinook Digital Media",
        "subtitle": "Tienda Digital Global de Música, Álbumes y Streaming",
        "emoji": "🎧",
        "kaggle_source": {
            "name": "Chinook Sample Database",
            "url": "https://www.kaggle.com/datasets/asjad99/chinook",
            "author": "Luis Rocha (Creador oficial de Chinook)",
            "license": "MIT License",
            "scope": "11 tablas, catálogo de canciones, clientes en más de 24 países y ventas digitales"
        },
        "non_technical_summary": (
            "Imagina que eres el vicepresidente de producto de una tienda digital de música global como iTunes Store "
            "o Bandcamp. Melómanos de todo el planeta entran a tu plataforma web para comprar canciones individuales o "
            "álbumes completos de Rock, Jazz, Metal, Pop, Blues y Música Clásica.\n\n"
            "La base de datos Chinook almacena todo el ecosistema de la industria discográfica moderna: los artistas y "
            "sus álbumes, la duración en milisegundos de cada pista, el formato digital (MPEG, AAC, protegido), los "
            "clientes compradores con sus direcciones de facturación en América, Europa y Asia, y los agentes de servicio "
            "al cliente que resuelven dudas o reclamos de facturación."
        ),
        "business_value": (
            "Es ideal para análisis de catálogo digital, rotación de artistas, estacionalidad de compras musicales por "
            "país y análisis de penetración por géneros musicales."
        ),
        "modules": [
            {
                "name": "Catálogo Musical & Discografía",
                "tables": ["Artist", "Album", "Track", "Genre", "MediaType"],
                "description": "Artistas, álbumes producidos, pistas musicales con tamaño y duración, géneros musicales y formatos técnicos de codificación de audio."
            },
            {
                "name": "Facturación y Cobranzas Digitales",
                "tables": ["Invoice", "InvoiceLine"],
                "description": "Comprobantes de pago electrónicos emitidos a clientes de todo el mundo con fechas, montos totales e identificación de pistas compradas."
            },
            {
                "name": "Clientes y Soporte Técnico",
                "tables": ["Customer", "Employee"],
                "description": "Base de usuarios registrados internacionalmente y el personal de atención y gerencia interna de la tienda."
            },
            {
                "name": "Curación y Listas de Reproducción",
                "tables": ["Playlist", "PlaylistTrack"],
                "description": "Listas de reproducción temáticas que agrupan colecciones de canciones para recomendación a usuarios."
            }
        ],
        "tables_detail": [
            {"table": "Artist", "desc": "Bandas y solistas (AC/DC, Iron Maiden, Queen, Chico Buarque, Miles Davis)."},
            {"table": "Album", "desc": "Discos grabados, vinculados directamente con su artista creador."},
            {"table": "Track", "desc": "Canciones individuales con precio unitario ($0.99 usualmente), duración y tamaño en bytes."},
            {"table": "Genre", "desc": "Géneros musicales (Rock, Latin, Metal, Alternative & Punk, Jazz, Blues, etc.)."},
            {"table": "MediaType", "desc": "Formatos de archivo (MPEG audio file, AAC audio file, Protected MPEG-4)."},
            {"table": "Invoice", "desc": "Facturas de compra con fecha, cliente comprador, total en dólares y país de cobro."},
            {"table": "InvoiceLine", "desc": "Renglones de la factura con el precio cobrado y la canción adquirida."},
            {"table": "Customer", "desc": "Compradores en EE.UU., Canadá, Brasil, Alemania, Francia, Reino Unido, etc."},
            {"table": "Employee", "desc": "Personal interno (Gerente General, Representantes de Soporte Comercial)."},
            {"table": "Playlist", "desc": "Listas de reproducción musicales (Music, TV Shows, Grunge, 90s Music)."},
            {"table": "PlaylistTrack", "desc": "Tabla intermedia que asocia pistas a listas de reproducción."}
        ],
        "mermaid_erd": """erDiagram
    ARTIST ||--|{ ALBUM : "compone"
    ALBUM ||--|{ TRACK : "contiene"
    GENRE ||--|{ TRACK : "clasifica"
    MEDIA_TYPE ||--|{ TRACK : "formatea"
    TRACK ||--|{ INVOICE_LINE : "comprado_en"
    INVOICE ||--|{ INVOICE_LINE : "detalla"
    CUSTOMER ||--|{ INVOICE : "paga"
    EMPLOYEE ||--|{ CUSTOMER : "asiste"
    EMPLOYEE ||--o{ EMPLOYEE : "reporta_a"
    PLAYLIST ||--|{ PLAYLIST_TRACK : "agrupa"
    TRACK ||--|{ PLAYLIST_TRACK : "listado_en"

    ARTIST {
        int ArtistId PK
        string Name
    }
    ALBUM {
        int AlbumId PK
        string Title
        int ArtistId FK
    }
    TRACK {
        int TrackId PK
        string Name
        int AlbumId FK
        int MediaTypeId FK
        int GenreId FK
        int Milliseconds
        float UnitPrice
    }
    GENRE {
        int GenreId PK
        string Name
    }
    INVOICE {
        int InvoiceId PK
        int CustomerId FK
        datetime InvoiceDate
        float Total
        string BillingCountry
    }
    INVOICE_LINE {
        int InvoiceLineId PK
        int InvoiceId FK
        int TrackId FK
        float UnitPrice
        int Quantity
    }
    CUSTOMER {
        int CustomerId PK
        string FirstName
        string LastName
        string Country
        int SupportRepId FK
    }
    EMPLOYEE {
        int EmployeeId PK
        string LastName
        string FirstName
        string Title
        int ReportsTo FK
    }""",
        "erd_explanation": (
            "1. Un Artista (ARTIST) graba uno o más Álbumes (ALBUM).\n"
            "2. Cada Álbum está compuesto por múltiples Canciones (TRACK), cada una clasificada en un Género (GENRE) y Formato (MEDIA_TYPE).\n"
            "3. Un Cliente (CUSTOMER) realiza compras facturadas en Facturas (INVOICE).\n"
            "4. Cada Factura se desglosa en Líneas de Factura (INVOICE_LINE) que apuntan a las canciones compradas.\n"
            "5. Cada Cliente tiene asignado un Empleado (EMPLOYEE) como representante de soporte."
        ),
        "example_queries": [
            {
                "query": "dame los 10 albumes mas vendidos por ano",
                "pattern": "Ranking Particionado por Ventana Temporal (Window Function)",
                "insight": "Identifica los 10 álbumes líderes de facturación en cada año de operación y su rotación histórica."
            },
            {
                "query": "top 5 países con mayor facturación en música digital",
                "pattern": "Distribución Geográfica de Ingresos",
                "insight": "Descubre los mercados nacionales que generan el mayor flujo de caja en streaming y descargas."
            },
            {
                "query": "cuáles son los 5 artistas con más pistas vendidas",
                "pattern": "Ranking Top N de Artistas",
                "insight": "Determina qué músicos generan mayor volumen de reproducciones para negociar derechos editoriales."
            },
            {
                "query": "géneros musicales más rentables y su facturación total",
                "pattern": "Análisis Categórico de Concentración",
                "insight": "Mide la cuota de mercado del Rock frente al Pop o Latin para optimizar campañas de recomendación."
            },
            {
                "query": "tendencia mensual de las ventas de música a través del tiempo",
                "pattern": "Serie Temporal Longitudinal",
                "insight": "Monitorea la estacionalidad de consumo (fiestas decembrinas, lanzamientos de mitad de año)."
            }
        ]
    },

    "sakila": {
        "id": "sakila",
        "title": "Sakila DVD Rental Store",
        "subtitle": "Cadena Minorista de Videoclubes, Películas e Inventario Físico",
        "emoji": "🎬",
        "kaggle_source": {
            "name": "Sakila Sample Database (SQLite)",
            "url": "https://www.kaggle.com/datasets/atharvaingle/sakila-sqlite",
            "author": "MySQL AB / Oracle Corporation",
            "license": "BSD License",
            "scope": "16 tablas normalizadas, tiendas físicas, catálogo de actores, alquileres y cobros en caja"
        },
        "non_technical_summary": (
            "Imagina que eres el gerente de operaciones de una famosa cadena de tiendas de alquiler de películas "
            "en DVD y Blu-ray como Blockbuster Video. Tienes sucursales físicas en distintas ciudades con miles de "
            "clientes abonados que acuden semanalmente a rentar estrenos cinematográficos.\n\n"
            "La base de datos Sakila modela la vida diaria de estas tiendas: el catálogo con 1,000 películas clasificadas "
            "por género (Acción, Comedia, Drama, Terror, Ciencia Ficción) y con sus actores protagonistas; el inventario "
            "físico de cuántas copias reales de cada título están en los estantes de cada sucursal; los préstamos efectuados "
            "en caja por los empleados y los pagos monetarios recibidos al momento de devolver la cinta."
        ),
        "business_value": (
            "Permite analizar la rentabilidad de las películas según sus costos de reposición, medir la tasa de devolución "
            "a tiempo, comparar el rendimiento entre sucursales y conocer qué actores atraen más alquileres."
        ),
        "modules": [
            {
                "name": "Catálogo Cinematográfico y Talento",
                "tables": ["film", "category", "actor", "film_actor", "film_category", "language"],
                "description": "Películas, años de estreno, sinopsis, duración, clasificación MPAA (PG, R, NC-17), actores participantes y categorías temáticas."
            },
            {
                "name": "Operaciones en Mostrador y Cobros",
                "tables": ["rental", "payment"],
                "description": "Eventos de retiro y devolución física de cintas, fechas de entrega y pagos monetarios registrados en caja registradora."
            },
            {
                "name": "Inventario de Sucursales",
                "tables": ["inventory", "store"],
                "description": "Copias físicas de cada disco presentes en el stock de cada tienda física y administradas por su respectivo gerente."
            },
            {
                "name": "Clientes, Empleados y Domicilios",
                "tables": ["customer", "staff", "address", "city", "country"],
                "description": "Usuarios registrados con estado activo/inactivo, cajeros de mostrador y jerarquía geográfica de direcciones urbanas."
            }
        ],
        "tables_detail": [
            {"table": "film", "desc": "Catálogo de largometrajes con duración, tarifa de alquiler, costo de reemplazo y rating."},
            {"table": "actor", "desc": "Actores y actrices participantes en las películas."},
            {"table": "category", "desc": "Géneros temáticos (Action, Comedy, Documentary, Drama, Family, Sci-Fi)."},
            {"table": "inventory", "desc": "Copias físicas individuales (DVDs) disponibles en las tiendas."},
            {"table": "rental", "desc": "Préstamos de películas: qué copia se llevó qué cliente y fecha de devolución."},
            {"table": "payment", "desc": "Cobros en caja por alquiler o recargos por demora."},
            {"table": "customer", "desc": "Clientes registrados con nombre, correo electrónico y tienda preferida."},
            {"table": "store", "desc": "Sucursales físicas con su respectivo gerente a cargo y dirección."},
            {"table": "staff", "desc": "Personal de mostrador que procesa los cobros y alquileres."},
            {"table": "address / city / country", "desc": "Normalización geográfica para tiendas y clientes."}
        ],
        "mermaid_erd": """erDiagram
    CATEGORY ||--|{ FILM_CATEGORY : "clasifica"
    FILM ||--|{ FILM_CATEGORY : "asociada_a"
    ACTOR ||--|{ FILM_ACTOR : "actua_en"
    FILM ||--|{ FILM_ACTOR : "reparto_de"
    LANGUAGE ||--|{ FILM : "idioma_de"
    FILM ||--|{ INVENTORY : "copias_fisicas"
    STORE ||--|{ INVENTORY : "almacena"
    INVENTORY ||--|{ RENTAL : "alquilado_en"
    CUSTOMER ||--|{ RENTAL : "presta"
    RENTAL ||--|{ PAYMENT : "cobrado_en"
    STAFF ||--|{ PAYMENT : "registra"
    STORE ||--|{ STAFF : "emplea"
    ADDRESS ||--|{ STORE : "ubicacion"
    ADDRESS ||--|{ CUSTOMER : "domicilio"
    CITY ||--|{ ADDRESS : "localidad"
    COUNTRY ||--|{ CITY : "nacion"

    FILM {
        int film_id PK
        string title
        int release_year
        float rental_rate
        int length
        float replacement_cost
        string rating
    }
    ACTOR {
        int actor_id PK
        string first_name
        string last_name
    }
    RENTAL {
        int rental_id PK
        datetime rental_date
        int inventory_id FK
        int customer_id FK
        datetime return_date
    }
    PAYMENT {
        int payment_id PK
        int customer_id FK
        int staff_id FK
        int rental_id FK
        float amount
        datetime payment_date
    }
    CUSTOMER {
        int customer_id PK
        int store_id FK
        string first_name
        string last_name
        int active
    }
    INVENTORY {
        int inventory_id PK
        int film_id FK
        int store_id FK
    }""",
        "erd_explanation": (
            "1. Una Película (FILM) cuenta con actores asociados mediante FILM_ACTOR y categorías mediante FILM_CATEGORY.\n"
            "2. Cada Tienda (STORE) mantiene copias físicas de las películas registradas en Inventario (INVENTORY).\n"
            "3. Un Cliente (CUSTOMER) genera un Alquiler (RENTAL) al retirar una copia física de inventario.\n"
            "4. Cada Alquiler genera un Pago (PAYMENT) procesado y cobrado en mostrador por un miembro del Personal (STAFF)."
        ),
        "example_queries": [
            {
                "query": "top 10 categorías de películas con mayor recaudación por alquiler",
                "pattern": "Ranking Top N de Ingresos",
                "insight": "Determina qué géneros cinematográficos aportan el mayor retorno financiero a las sucursales."
            },
            {
                "query": "top 5 actores con más apariciones en películas",
                "pattern": "Análisis de Frecuencia de Catálogo",
                "insight": "Conoce los artistas con mayor presencia en inventario para diseñar promociones y exhibidores."
            },
            {
                "query": "evolución de los ingresos por alquileres a través del tiempo",
                "pattern": "Serie Temporal de Ingresos",
                "insight": "Analiza las tendencias de demanda mensual y los picos de fin de semana en las tiendas."
            },
            {
                "query": "clientes con mayor volumen de alquileres realizados",
                "pattern": "Segmentación de Clientes Frecuentes",
                "insight": "Identifica al segmento de compradores VIP para programas de fidelización y membresías."
            },
            {
                "query": "distribución de películas por clasificación de edades",
                "pattern": "Distribución Categórica",
                "insight": "Evalúa el balance del catálogo entre público familiar (G, PG) y adulto (R, NC-17)."
            }
        ]
    },

    "adventureworks_dw": {
        "id": "adventureworks_dw",
        "title": "AdventureWorks Cycles",
        "subtitle": "Manufactura Multinacional de Bicicletas, Componentes y Data Warehouse",
        "emoji": "🚲",
        "kaggle_source": {
            "name": "AdventureWorks SQLite Database",
            "url": "https://www.kaggle.com/datasets/algorismus/adventure-works-in-sqlite",
            "author": "Microsoft Corporation (Port SQLite Data Warehouse)",
            "license": "Microsoft Open License",
            "scope": "12 tablas, ingeniería de productos, fabricación, órdenes mayoristas y costos estándar"
        },
        "non_technical_summary": (
            "Imagina que lideras la dirección financiera y de operaciones de 'AdventureWorks Cycles', una gran "
            "compañía multinacional de manufactura que diseña y ensambla bicicletas de montaña, de ruta y de paseo, "
            "además de fabricar componentes mecánicos (frenos, pedales, cadenas) y prendas de ropa deportiva de alta gama.\n\n"
            "Esta base de datos es un modelo Data Warehouse empresarial: registra las especificaciones de ingeniería "
            "de cada modelo con sus fichas técnicas en varios idiomas, los costos de fabricación frente al precio oficial "
            "de lista para calcular márgenes brutos, los pedidos mayoristas de distribuidores globales y las direcciones "
            "geográficas de entrega."
        ),
        "business_value": (
            "Permite optimizar márgenes brutos de producción, analizar la rentabilidad por modelo y línea de producto, "
            "detectar productos con costo de manufactura desbalanceado y planificar la capacidad de planta."
        ),
        "modules": [
            {
                "name": "Ingeniería de Productos y Modelos",
                "tables": ["Product", "ProductCategory", "ProductModel", "ProductDescription", "ProductModelProductDescription"],
                "description": "Catálogo industrial con jerarquía de categorías, modelos base de ingeniería, descripciones multilingües (inglés, español, francés, chino), costos estándar y precios de lista."
            },
            {
                "name": "Órdenes de Venta y Facturación",
                "tables": ["SalesOrderHeader", "SalesOrderDetail"],
                "description": "Transacciones de venta mayorista y retail: fechas de pedido, fletes marítimos, impuestos calculados y renglones de producto vendidos con totales de línea."
            },
            {
                "name": "Clientes y Direcciones Corporativas",
                "tables": ["Customer", "CustomerAddress", "Address"],
                "description": "Distribuidores comerciales y clientes finales con nombres, empresas asociadas y localización geográfica de envío."
            },
            {
                "name": "Control del Sistema y Metadatos",
                "tables": ["BuildVersion", "ErrorLog"],
                "description": "Auditoría de versiones de la base de datos y registro de excepciones del sistema ERP."
            }
        ],
        "tables_detail": [
            {"table": "Product", "desc": "Artículos producidos con costo estándar de manufactura, precio de lista, color y tamaño."},
            {"table": "ProductCategory", "desc": "Categorías jerárquicas (Bikes, Components, Clothing, Accessories)."},
            {"table": "ProductModel", "desc": "Modelos madre de ingeniería (Mountain-100, Road-250, Touring-3000)."},
            {"table": "ProductDescription", "desc": "Textos explicativos de mercadeo y características técnicas del artículo."},
            {"table": "SalesOrderHeader", "desc": "Cabecera de órdenes de venta con subtotal, flete, impuestos y total facturado."},
            {"table": "SalesOrderDetail", "desc": "Detalle de cantidades ordenadas por producto y precio unitario pactado."},
            {"table": "Customer", "desc": "Cuentas corporativas y personas con nombres, empresa y contacto."},
            {"table": "Address", "desc": "Direcciones físicas de entrega con ciudad, estado y código postal."},
            {"table": "CustomerAddress", "desc": "Vínculo de tipos de dirección (facturación vs despacho) por cliente."}
        ],
        "mermaid_erd": """erDiagram
    PRODUCT_CATEGORY ||--o{ PRODUCT_CATEGORY : "subcategoria_de"
    PRODUCT_CATEGORY ||--|{ PRODUCT : "clasifica"
    PRODUCT_MODEL ||--|{ PRODUCT : "modelo_base"
    PRODUCT_MODEL ||--|{ PRODUCT_MODEL_PRODUCT_DESCRIPTION : "documenta"
    PRODUCT_DESCRIPTION ||--|{ PRODUCT_MODEL_PRODUCT_DESCRIPTION : "texto"
    PRODUCT ||--|{ SALES_ORDER_DETAIL : "vendido_en"
    SALES_ORDER_HEADER ||--|{ SALES_ORDER_DETAIL : "detalla"
    CUSTOMER ||--|{ SALES_ORDER_HEADER : "ordena"
    CUSTOMER ||--|{ CUSTOMER_ADDRESS : "tiene"
    ADDRESS ||--|{ CUSTOMER_ADDRESS : "ubicacion"

    PRODUCT {
        int ProductID PK
        string Name
        string ProductNumber
        float StandardCost
        float ListPrice
        int ProductCategoryID FK
        int ProductModelID FK
    }
    PRODUCT_CATEGORY {
        int ProductCategoryID PK
        int ParentProductCategoryID FK
        string Name
    }
    SALES_ORDER_HEADER {
        int SalesOrderID PK
        datetime OrderDate
        int CustomerID FK
        float SubTotal
        float TaxAmt
        float Freight
        float TotalDue
    }
    SALES_ORDER_DETAIL {
        int SalesOrderID PK,FK
        int SalesOrderDetailID PK
        int OrderQty
        int ProductID FK
        float UnitPrice
        float LineTotal
    }
    CUSTOMER {
        int CustomerID PK
        string FirstName
        string LastName
        string CompanyName
    }""",
        "erd_explanation": (
            "1. Un Modelo de Producto (PRODUCT_MODEL) define las líneas de diseño industrial y sus fichas (PRODUCT_DESCRIPTION).\n"
            "2. Cada Producto específico (PRODUCT) se clasifica en una Categoría (PRODUCT_CATEGORY) y define su precio y costo.\n"
            "3. Los Clientes (CUSTOMER) emiten Órdenes de Venta (SALES_ORDER_HEADER) asociadas a una Dirección (ADDRESS).\n"
            "4. Cada Orden se desglosa en renglones en Detalle de Venta (SALES_ORDER_DETAIL), vinculando las unidades de Producto vendidas."
        ),
        "example_queries": [
            {
                "query": "top 5 productos con mayor facturación en ventas",
                "pattern": "Ranking Top N de Ingresos",
                "insight": "Conoce los modelos de bicicletas y componentes que sustentan la mayor porción del flujo de caja."
            },
            {
                "query": "cuáles son las categorías con mayor margen entre costo de manufactura y precio de lista",
                "pattern": "Análisis de Rentabilidad Industrial",
                "insight": "Compara si los accesorios y prendas de vestir generan más margen porcentual que las bicicletas armadas."
            },
            {
                "query": "top 5 clientes con mayor volumen de compras acumuladas",
                "pattern": "Concentración de Cuentas B2B",
                "insight": "Mide el riesgo de dependencia comercial sobre los distribuidores mayoristas clave."
            },
            {
                "query": "distribución de productos por categoría y modelo",
                "pattern": "Diagnóstico de Variedad de Catálogo",
                "insight": "Evalúa la complejidad del portafolio industrial para consolidar SKUs redundantes."
            }
        ]
    },

    "tpch": {
        "id": "tpch",
        "title": "TPC-H Benchmark",
        "subtitle": "Estándar Global de Cadena de Suministro, Fletes y Soporte de Decisiones",
        "emoji": "🌐",
        "kaggle_source": {
            "name": "TPC-H Database & Benchmark Suite",
            "url": "https://www.kaggle.com/datasets/gaborfodor/tpc-h-sqlite",
            "author": "Transaction Processing Performance Council (TPC)",
            "license": "TPC Benchmark Standard Open Specification",
            "scope": "8 tablas normalizadas, estándar mundial para Big Data, logística pesada y analítica OLAP"
        },
        "non_technical_summary": (
            "Imagina una red internacional de cadena de suministro (Supply Chain) e industria pesada a escala planetaria. "
            "Proveedores de acero, cobre, piezas mecánicas y maquinaria pesada abastecen a miles de corporaciones manufactureras "
            "repartidas en 25 naciones y 5 grandes continentes (América, Europa, Asia, África y Medio Oriente).\n\n"
            "TPC-H es el estándar de oro más respetado en la historia de la computación para medir la capacidad de análisis "
            "de decisiones estratégicas: pedidos multimillonarios que requieren fletes marítimos, descuentos por volumen "
            "negociados entre gerentes de compras, evaluación de la solvencia financiera de los clientes y auditoría de retrasos "
            "en las fechas de recepción de mercancía."
        ),
        "business_value": (
            "Es el laboratorio analítico definitivo para analizar la concentración geopolítica del suministro, "
            "tiempos de tránsito logístico, impacto de los descuentos comerciales en el margen y desempeño de proveedores."
        ),
        "modules": [
            {
                "name": "Pedidos Corporativos y Líneas de Embarque",
                "tables": ["orders", "lineitem"],
                "description": "Grandes órdenes de compra y cada uno de sus despachos con precios extendidos, descuentos contractuales, recargos de impuestos, prioridad de entrega (Urgent, High, Medium, Low) y modo de transporte (FOB, Ship, Air, Rail, Truck)."
            },
            {
                "name": "Catálogo de Piezas Industriales y Proveedores",
                "tables": ["part", "supplier", "partsupp"],
                "description": "Piezas técnicas clasificadas por marca y material, red global de proveedores con saldos contables y matriz conjunta de costo de suministro y disponibilidad de stock."
            },
            {
                "name": "Compradores y Segmentos de Mercado",
                "tables": ["customer"],
                "description": "Empresas compradoras con saldos financieros y clasificadas en 5 segmentos industriales: Automobile, Building, Machinery, Household y Furniture."
            },
            {
                "name": "Geografía Continental y Países",
                "tables": ["nation", "region"],
                "description": "Jerarquía geográfica que agrupa 25 naciones representativas dentro de 5 macro-regiones continentales."
            }
        ],
        "tables_detail": [
            {"table": "orders", "desc": "Pedidos de compra con estado (Open, Closed), precio total, fecha de emisión y prioridad."},
            {"table": "lineitem", "desc": "Renglones de flete y despacho con cantidad, precio extendido, descuento y modo de envío."},
            {"table": "part", "desc": "Piezas industriales con fabricante, marca, tipo y precio de venta al público."},
            {"table": "supplier", "desc": "Proveedores con balance de cuenta contable y dirección en su país respectivo."},
            {"table": "partsupp", "desc": "Matriz de abastecimiento: qué proveedor tiene qué pieza, cuántas en stock y a qué costo."},
            {"table": "customer", "desc": "Clientes corporativos con saldo financiero y segmento de mercado."},
            {"table": "nation", "desc": "25 naciones del mundo (Argentina, Brasil, Canadá, Alemania, China, etc.)."},
            {"table": "region", "desc": "5 regiones continentales (América, Europa, Asia, África, Medio Oriente)."}
        ],
        "mermaid_erd": """erDiagram
    REGION ||--|{ NATION : "contiene"
    NATION ||--|{ CUSTOMER : "ubica"
    NATION ||--|{ SUPPLIER : "ubica"
    SUPPLIER ||--|{ PARTSUPP : "provee"
    PART ||--|{ PARTSUPP : "abastecido_por"
    PARTSUPP ||--|{ LINEITEM : "despachado_en"
    ORDERS ||--|{ LINEITEM : "contiene"
    CUSTOMER ||--|{ ORDERS : "solicita"

    CUSTOMER {
        int c_custkey PK
        string c_name
        int c_nationkey FK
        float c_acctbal
        string c_mktsegment
    }
    ORDERS {
        int o_orderkey PK
        int o_custkey FK
        string o_orderstatus
        float o_totalprice
        datetime o_orderdate
        string o_orderpriority
    }
    LINEITEM {
        int l_orderkey PK,FK
        int l_linenumber PK
        int l_partkey FK
        int l_suppkey FK
        float l_quantity
        float l_extendedprice
        float l_discount
        float l_tax
        string l_shipmode
    }
    PART {
        int p_partkey PK
        string p_name
        string p_mfgr
        string p_brand
        string p_type
        float p_retailprice
    }
    SUPPLIER {
        int s_suppkey PK
        string s_name
        int s_nationkey FK
        float s_acctbal
    }
    PARTSUPP {
        int ps_partkey PK,FK
        int ps_suppkey PK,FK
        int ps_availqty
        float ps_supplycost
    }
    NATION {
        int n_nationkey PK
        string n_name
        int n_regionkey FK
    }
    REGION {
        int r_regionkey PK
        string r_name
    }""",
        "erd_explanation": (
            "1. Cada Región Continental (REGION) contiene múltiples Naciones (NATION).\n"
            "2. Tanto Clientes (CUSTOMER) como Proveedores (SUPPLIER) radican en una Nación específica.\n"
            "3. Los Proveedores suministran Piezas (PART) a través de la relación de inventario y costo (PARTSUPP).\n"
            "4. Un Cliente emite Pedidos (ORDERS), los cuales se desglosan en Líneas de Embarque (LINEITEM) asociadas a las piezas provistas."
        ),
        "example_queries": [
            {
                "query": "facturación total de compras por región geográfica",
                "pattern": "Distribución Macro-Continental",
                "insight": "Compara el volumen comercial entre América, Europa, Asia y África para enfocar la logística global."
            },
            {
                "query": "top 5 proveedores con mayor volumen de piezas suministradas",
                "pattern": "Ranking de Socios Estratégicos",
                "insight": "Detecta qué fabricantes son el pilar de la cadena de suministro para negociar mejores acuerdos de flete."
            },
            {
                "query": "distribución de pedidos por prioridad y estado de embarque",
                "pattern": "Diagnóstico de Eficiencia Logística",
                "insight": "Mide qué porcentaje de órdenes marcadas como urgentes presentan retrasos en el flete marítimo."
            },
            {
                "query": "ventas totales y descuento promedio por segmento de mercado",
                "pattern": "Segmentación B2B de Clientes",
                "insight": "Evalúa si el segmento de Automóviles recibe más descuentos que el de Maquinaria pesada."
            },
            {
                "query": "tendencia anual de las órdenes de compra globales",
                "pattern": "Serie Temporal de Pedidos",
                "insight": "Proyecta la demanda de abastecimiento y la necesidad de bodegaje para los próximos años fiscales."
            }
        ]
    },
    "el_salvador": {
        "id": "el_salvador",
        "title": "El Salvador Data & Intelligence Hub",
        "subtitle": "Censo Nacional 2024 de Población, Reestructuración Territorial, Macroeconomía BCR & Clima MARN",
        "emoji": "🇸🇻",
        "kaggle_source": {
            "name": "BCR El Salvador Geoportal & MARN Clima Open Datasets",
            "url": "https://estadisticas.bcr.gob.sv",
            "author": "Banco Central de Reserva (BCR) & Ministerio de Medio Ambiente (MARN)",
            "license": "Datos Públicos Abiertos Oficiales",
            "scope": "7 tablas relacionales: 14 departamentos, 44 municipios consolidados, 262 distritos, 12,880 registros censales, series mensuales de remesas e IPC, e indicadores climáticos"
        },
        "non_technical_summary": (
            "Imagina que eres un ministro, consultor de políticas públicas o director de inversiones que necesita entender "
            "con precisión quirúrgica la realidad territorial y económica de El Salvador.\n\n"
            "Esta base de datos integra por primera vez tres pilares fundamentales del país:\n"
            "1. El Censo Nacional de Población 2024 publicado por el Banco Central de Reserva (BCR), adaptado a la nueva ley "
            "de reestructuración territorial de 14 departamentos, 44 municipios y 262 distritos históricos, con desglose exhaustivo "
            "por género y rangos quinquenales de edad.\n"
            "2. La macroeconomía nacional del BCR: la serie histórica mensual de remesas familiares (el motor financiero de cientos "
            "de miles de hogares, cuantificado en millones de dólares) y el Índice de Precios al Consumidor (IPC) para medir inflación "
            "y poder adquisitivo.\n"
            "3. El clima del Ministerio de Medio Ambiente y Recursos Naturales (MARN): registro de eventos hidrometeorológicos, "
            "temperaturas récord, sequías y olas de calor por departamento y estación.\n\n"
            "Gracias a esta integración, puedes responder con datos exactos desde cuántas personas viven en Santa Ana Centro, "
            "hasta cómo han evolucionado las remesas mes a mes o qué departamento sufrió la mayor anomalía de lluvia."
        ),
        "business_value": (
            "Permite a organismos multilaterales, entidades financieras y planificadores gubernamentales modelar el impacto "
            "demográfico de proyectos, focalizar programas sociales según grupos etarios, correlacionar la recepción de divisas con "
            "la inflación y evaluar riesgos climáticos sobre la infraestructura y la agricultura nacional."
        ),
        "modules": [
            {
                "name": "División Política y Territorial 2024",
                "tables": ["departamentos", "municipios", "distritos"],
                "description": "Jerarquía geográfica completa: los 14 departamentos tradicionales, los 44 municipios reestructurados tras la ley 2024 y los 262 distritos municipales históricos."
            },
            {
                "name": "Demografía Censal BCR 2024",
                "tables": ["censo_poblacion"],
                "description": "12,880 filas con recuentos poblacionales por departamento, municipio, distrito, género y rangos de edad."
            },
            {
                "name": "Macroeconomía y Finanzas Familiares",
                "tables": ["remesas_mensuales", "ipc_mensual"],
                "description": "Series temporales mensuales del BCR: ingresos de divisas por remesas en millones de USD e índice de inflación nacional."
            },
            {
                "name": "Medio Ambiente y Climatología",
                "tables": ["clima_indicadores"],
                "description": "Indicadores anuales y por evento del MARN: precipitaciones máximas, anomalías térmicas y días de olas de calor enlazados a departamentos."
            }
        ],
        "tables_detail": [
            {"table": "departamentos", "desc": "Los 14 departamentos de El Salvador clasificados por zona (Occidental, Central, Paracentral, Oriental)."},
            {"table": "municipios", "desc": "Los 44 municipios de la reforma territorial de 2024 enlazados a sus departamentos."},
            {"table": "distritos", "desc": "Los 262 distritos históricos vinculados a sus respectivos municipios y departamentos."},
            {"table": "censo_poblacion", "desc": "Población censada en 2024 por nivel geográfico, rango quinquenal de edad y género."},
            {"table": "remesas_mensuales", "desc": "Ingresos mensuales por remesas familiares en millones de USD del BCR."},
            {"table": "ipc_mensual", "desc": "Índice de Precios al Consumidor mensual base 2009=100 publicado por el BCR."},
            {"table": "clima_indicadores", "desc": "Indicadores climáticos del MARN (lluvias, temperaturas, sequías) vinculados a departamentos."}
        ],
        "mermaid_erd": """erDiagram
    DEPARTAMENTOS ||--|{ MUNICIPIOS : "agrupa"
    MUNICIPIOS ||--|{ DISTRITOS : "contiene"
    DEPARTAMENTOS ||--|{ DISTRITOS : "ubica"
    DEPARTAMENTOS ||--|{ CENSO_POBLACION : "censado_en"
    MUNICIPIOS ||--|{ CENSO_POBLACION : "censado_en"
    DISTRITOS ||--|{ CENSO_POBLACION : "censado_en"
    DEPARTAMENTOS ||--o{ CLIMA_INDICADORES : "registrado_en"

    DEPARTAMENTOS {
        string departamento_id PK
        string departamento_nombre
        string zona_geografica
    }
    MUNICIPIOS {
        string municipio_id PK
        string departamento_id FK
        string municipio_nombre
    }
    DISTRITOS {
        string distrito_id PK
        string municipio_id FK
        string departamento_id FK
        string distrito_nombre
    }
    CENSO_POBLACION {
        int id PK
        int censo_anio
        string departamento_id FK
        string municipio_id FK
        string distrito_id FK
        string nivel_geografico
        string rango_edad
        string genero
        int poblacion
    }
    REMESAS_MENSUALES {
        int id PK
        string periodo
        float monto_millones_usd
        string fuente
        string frecuencia
        int es_preliminar
    }
    IPC_MENSUAL {
        int id PK
        string periodo
        float indice
        string serie
        string base_indice
        string fuente
    }
    CLIMA_INDICADORES {
        int id PK
        int anio
        string indicador
        float valor
        string unidad
        string estacion
        string departamento_id FK
        string periodo_inicio
        string periodo_fin
        string anotacion
    }""",
        "erd_explanation": (
            "1. La jerarquía territorial enlaza Departamentos (DEPARTAMENTOS) -> Municipios (MUNICIPIOS) -> Distritos (DISTRITOS).\n"
            "2. El Censo de Población (CENSO_POBLACION) contiene llaves foráneas a los 3 niveles geográficos para permitir análisis a escala nacional, departamental, municipal o distrital.\n"
            "3. Los Indicadores Climatológicos (CLIMA_INDICADORES) se enlazan con Departamentos para evaluar eventos climáticos por territorio.\n"
            "4. Las Remesas Mensuales (REMESAS_MENSUALES) y el IPC (IPC_MENSUAL) proporcionan las series históricas macroeconómicas nacionales."
        ),
        "example_queries": [
            {
                "query": "cuál es la población por departamento",
                "pattern": "Distribución Demográfica Departamental",
                "insight": "Compara el peso poblacional de los 14 departamentos según el Censo Nacional 2024."
            },
            {
                "query": "remesas mensuales",
                "pattern": "Serie Temporal de Remesas Familiares",
                "insight": "Evalúa el flujo mensual de divisas hacia El Salvador y detecta estacionalidades."
            },
            {
                "query": "evolución mensual del índice de precios al consumidor ipc",
                "pattern": "Monitoreo de Inflación Nacional",
                "insight": "Mide el comportamiento del costo de vida y estabilidad de precios para las familias salvadoreñas."
            },
            {
                "query": "top 10 distritos más poblados",
                "pattern": "Ranking de Densidad Urbana Local",
                "insight": "Identifica los núcleos distritales con mayor demanda de servicios públicos y transporte."
            },
            {
                "query": "indicadores de lluvia y clima por departamento",
                "pattern": "Diagnóstico de Vulnerabilidad Climática",
                "insight": "Detecta qué departamentos registraron los mayores volúmenes de precipitación y anomalías térmicas."
            },
            {
                "query": "distribución de población por género",
                "pattern": "Composición Demográfica por Género",
                "insight": "Analiza la proporción de hombres y mujeres en la pirámide poblacional del censo 2024."
            }
        ]
    }
}


def get_database_doc(engine_id: str) -> dict[str, Any] | None:
    """Returns the documentation metadata for a specific engine."""
    return DATABASE_CATALOG.get(engine_id.lower())


def get_all_database_docs() -> list[dict[str, Any]]:
    """Returns all database documentation entries."""
    return list(DATABASE_CATALOG.values())


def render_database_docs_section_html() -> str:
    """Renders the comprehensive database catalog section for the standalone docs portal."""
    cards_html = []

    for doc in DATABASE_CATALOG.values():
        kaggle = doc["kaggle_source"]
        non_tech_html = doc["non_technical_summary"].replace("\n\n", "<br><br>")
        modules_html = "".join([
            f"""
            <div class="bg-slate-900/60 border border-slate-800/80 p-3.5 rounded-xl">
                <div class="flex items-center justify-between mb-1.5">
                    <h5 class="text-xs font-bold text-indigo-300">{mod['name']}</h5>
                    <span class="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded">{", ".join(mod['tables'])}</span>
                </div>
                <p class="text-xs text-slate-300 leading-relaxed">{mod['description']}</p>
            </div>
            """
            for mod in doc["modules"]
        ])

        examples_html = "".join([
            f"""
            <div class="bg-slate-900/40 border border-slate-800/80 p-3 rounded-xl flex flex-col justify-between hover:border-indigo-500/40 transition">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-1.5">
                        <span class="text-[10px] uppercase tracking-wider font-semibold text-indigo-400 font-mono bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-900/50">{ex['pattern']}</span>
                    </div>
                    <p class="text-xs font-medium text-white mb-1.5 flex items-start gap-1.5">
                        <span class="text-indigo-400">💬</span> "{ex['query']}"
                    </p>
                    <p class="text-[11px] text-slate-400 leading-snug">{ex['insight']}</p>
                </div>
                <div class="mt-3 pt-2 border-t border-slate-800/60 flex justify-end">
                    <a href="/?engine={doc['id']}&q={ex['query']}" class="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1 transition">
                        <span>⚡ Probar en Dashboard</span> &rarr;
                    </a>
                </div>
            </div>
            """
            for ex in doc["example_queries"]
        ])

        tables_pills = "".join([
            f"""<span class="text-[11px] font-mono bg-slate-900 border border-slate-800 px-2 py-1 rounded text-slate-300" title="{t['desc']}">{t['table']}</span>"""
            for t in doc["tables_detail"]
        ])

        card = f"""
        <article id="database-{doc['id']}" class="bg-slate-900/60 border border-slate-800 p-6 md:p-8 rounded-2xl space-y-6">
            <!-- Header de la Base de Datos -->
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b border-slate-800">
                <div class="flex items-center gap-3">
                    <span class="text-3xl p-2.5 rounded-xl bg-slate-950 border border-slate-800">{doc['emoji']}</span>
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-xl font-bold text-white tracking-wide">{doc['title']}</h3>
                            <span class="text-xs font-mono font-bold bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded border border-indigo-800">{doc['id'].upper()}</span>
                        </div>
                        <p class="text-xs md:text-sm text-slate-400 mt-0.5">{doc['subtitle']}</p>
                    </div>
                </div>

                <!-- Kaggle Primary Source Badge -->
                <div class="bg-slate-950 border border-slate-800/90 p-3 rounded-xl flex items-center gap-3 text-xs w-full md:w-auto">
                    <div class="text-xl">📊</div>
                    <div>
                        <div class="flex items-center gap-1.5">
                            <span class="font-bold text-sky-400">Kaggle Dataset</span>
                            <span class="text-[10px] text-slate-500">• {kaggle['license']}</span>
                        </div>
                        <a href="{kaggle['url']}" target="_blank" rel="noopener noreferrer" class="text-indigo-400 hover:text-indigo-300 underline font-medium truncate block max-w-xs">
                            {kaggle['name']} &nearr;
                        </a>
                        <p class="text-[10px] text-slate-400 mt-0.5">{kaggle['author']}</p>
                    </div>
                </div>
            </div>

            <!-- Explicación No Técnica (En Cristiano) -->
            <div class="bg-slate-950/80 border border-slate-800 p-5 rounded-xl">
                <h4 class="text-xs font-bold uppercase tracking-wider text-indigo-400 mb-2 flex items-center gap-2">
                    <span>💡</span> ¿En qué consiste esta base de datos? (Explicación para personas no técnicas)
                </h4>
                <div class="text-slate-300 text-sm leading-relaxed space-y-3">
                    {non_tech_html}
                </div>
                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-xs text-emerald-400">
                    <span>🎯</span> <strong>Valor de Decisión Ejecutiva:</strong> <span class="text-slate-300">{doc['business_value']}</span>
                </div>
            </div>

            <!-- Módulos de Información y Tablas -->
            <div>
                <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                    <span>📦</span> ¿Qué información contiene? (Módulos de Negocio)
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                    {modules_html}
                </div>
                <div class="flex flex-wrap items-center gap-1.5 pt-2">
                    <span class="text-xs text-slate-500 font-semibold mr-1">Tablas ({len(doc['tables_detail'])}):</span>
                    {tables_pills}
                </div>
            </div>

            <!-- Diagrama ER Interactivo con Archify & Modelo General -->
            <div>
                <div class="flex flex-wrap items-center justify-between mb-2.5 gap-2">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">🗺️</span>
                        <h4 class="text-xs font-bold uppercase tracking-wider text-slate-300">
                            Modelo Entidad-Relación (Archify ERD 100% Atributos & Relaciones)
                        </h4>
                    </div>
                    <div class="flex items-center gap-2">
                        <a href="/api/archify/engine/{doc['id']}.html" target="_blank" class="px-2.5 py-1 text-xs rounded bg-slate-900 border border-slate-800 text-sky-400 hover:text-white hover:border-sky-500 transition flex items-center gap-1 font-mono">
                            <span>⇱ Pantalla Completa</span>
                        </a>
                    </div>
                </div>

                <!-- Archify Interactive Visual Card -->
                <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl mb-4">
                    <div class="flex items-center justify-between px-3.5 py-2 bg-slate-900/90 border-b border-slate-800 text-xs">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span class="font-mono text-slate-300 text-[11px] font-semibold">Archify Canvas &bull; {doc['id'].upper()}</span>
                            <span class="text-[10px] font-mono bg-sky-950/80 text-sky-300 border border-sky-800/60 px-1.5 py-0.5 rounded">Interactivo (Zoom / Drag)</span>
                        </div>
                        <span class="text-[10px] font-mono text-slate-400">Todos los atributos y tipos físicos</span>
                    </div>
                    <div class="w-full h-[520px] bg-[#0b0f19]">
                        <iframe src="/api/archify/engine/{doc['id']}.html?theme=dark&embed=1" class="w-full h-full border-0 rounded-b-xl" loading="lazy"></iframe>
                    </div>
                </div>

                <!-- Relaciones en Cristiano & Mermaid Spec -->
                <div class="grid grid-cols-1 gap-3">
                    <div class="bg-slate-950 border border-slate-800/80 p-4 rounded-xl text-xs text-slate-300">
                        <strong class="text-indigo-300 flex items-center gap-1.5 mb-1">
                            <span>💡</span> ¿Cómo se relacionan las tablas en cristiano?
                        </strong>
                        <div class="space-y-1 text-slate-400 whitespace-pre-line leading-relaxed text-xs">
{doc['erd_explanation']}
                        </div>
                    </div>

                    <details class="group bg-slate-950/60 border border-slate-800/60 rounded-xl p-3 text-xs">
                        <summary class="cursor-pointer text-slate-400 hover:text-slate-200 font-mono text-[11px] flex items-center justify-between select-none">
                            <span>📜 Ver especificación formal Mermaid ERD</span>
                            <span class="group-open:rotate-180 transition-transform">▼</span>
                        </summary>
                        <div class="mermaid mt-3">
{doc['mermaid_erd']}
                        </div>
                    </details>
                </div>
            </div>

            <!-- Consultas de Ejemplo en Lenguaje Natural -->
            <div>
                <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                    <span>💬</span> ¿Cómo utilizarla? Consultas de ejemplo en lenguaje natural
                </h4>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {examples_html}
                </div>
            </div>
        </article>
        """
        cards_html.append(card)

    return f"""
    <!-- Sección de Catálogo de Bases de Datos -->
    <section id="databases" class="space-y-8">
        <div class="bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-950 border border-indigo-900/30 p-6 md:p-8 rounded-2xl">
            <div class="flex items-center gap-3 mb-2">
                <span class="text-3xl">🗄️</span>
                <h2 class="text-2xl font-bold text-white tracking-wide">Catálogo de Bases de Datos & Modelos ER Generales (Archify)</h2>
            </div>
            <p class="text-slate-300 text-sm md:text-base leading-relaxed max-w-4xl">
                Kratos integra 6 bases de datos reales del estándar mundial (disponibles en <strong>Kaggle</strong> y fuentes oficiales de <strong>El Salvador</strong>) que representan
                diversos modelos de negocio y analítica: comercio B2B, tiendas de música digital, videoclubes de retail físico,
                manufactura industrial, logística internacional y demografía/macroeconomía territorial de El Salvador.
                Todos los modelos de entidad-relación se visualizan interactivamente mediante <strong>Archify</strong> con 100% de atributos y claves.
            </p>
            <div class="flex flex-wrap gap-2 mt-4 text-xs font-mono">
                <a href="#database-northwind" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-900/60 border border-slate-800 text-slate-300 hover:text-white transition">🚢 NORTHWIND</a>
                <a href="#database-chinook" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-900/60 border border-slate-800 text-slate-300 hover:text-white transition">🎧 CHINOOK</a>
                <a href="#database-sakila" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-900/60 border border-slate-800 text-slate-300 hover:text-white transition">🎬 SAKILA</a>
                <a href="#database-adventureworks_dw" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-900/60 border border-slate-800 text-slate-300 hover:text-white transition">🚲 ADVENTUREWORKS_DW</a>
                <a href="#database-tpch" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-indigo-900/60 border border-slate-800 text-slate-300 hover:text-white transition">🌐 TPCH</a>
                <a href="#database-el_salvador" class="px-3 py-1.5 rounded-lg bg-indigo-900/50 hover:bg-indigo-800/60 border border-indigo-700/80 text-indigo-200 hover:text-white transition font-semibold">🇸🇻 EL_SALVADOR</a>
            </div>
        </div>

        <div class="space-y-10">
            {"".join(cards_html)}
        </div>
    </section>
    """
