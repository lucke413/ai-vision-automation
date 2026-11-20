<?php
/** Navigation shortcuts for the offers archive and long articles. */

function aivision_offers_overview( $query ) {
    if ( ! $query->is_main_query() || ! $query->is_category( 'offerte-2' ) || $query->is_paged() ) {
        return;
    }
    $posts = get_posts( array(
        'cat' => get_queried_object_id(),
        'post_type' => 'post',
        'post_status' => 'publish',
        'has_password' => false,
        'posts_per_page' => 18,
    ) );
    $groups = array( 'Ultime selezioni' => array(), 'Black Friday e campagne' => array() );
    foreach ( $posts as $entry ) {
        $title = get_the_title( $entry );
        $campaign = preg_match( '/\b(?:Black Friday|Cyber Monday|Prime Day|Festa delle offerte|Mese della Lettura|Amazon Gaming Week)\b/iu', $title );
        $group = $campaign ? 'Black Friday e campagne' : 'Ultime selezioni';
        if ( count( $groups[ $group ] ) < 3 ) {
            $groups[ $group ][] = $entry;
        }
    }
    ?>
    <div class="col-12 aiv-offers-overview-wrap">
        <nav class="aiv-offers-overview" aria-label="Esplora le offerte">
            <?php foreach ( $groups as $label => $entries ) : ?>
                <?php if ( $entries ) : ?>
                    <section>
                        <h2><?php echo esc_html( $label ); ?></h2>
                        <ul>
                            <?php foreach ( $entries as $entry ) : ?>
                                <li>
                                    <a href="<?php echo esc_url( get_permalink( $entry ) ); ?>"><?php echo esc_html( get_the_title( $entry ) ); ?></a>
                                    <time datetime="<?php echo esc_attr( get_the_date( 'Y-m-d', $entry ) ); ?>"><?php echo esc_html( get_the_date( 'j M', $entry ) ); ?></time>
                                </li>
                            <?php endforeach; ?>
                        </ul>
                    </section>
                <?php endif; ?>
            <?php endforeach; ?>
            <a class="aiv-offers-archive-link" href="#aiv-offers-archive">Vai all’archivio <span aria-hidden="true">↓</span></a>
        </nav>
        <div id="aiv-offers-archive" class="aiv-offers-archive-heading">
            <h2>Archivio offerte</h2>
            <p>Le selezioni sono ordinate per data di pubblicazione. Prezzo e disponibilità possono cambiare.</p>
        </div>
    </div>
    <?php
}

function aivision_article_outline( $content ) {
    if ( ! is_singular( 'post' ) || ! is_main_query() || ! in_the_loop() || is_feed()
            || false !== strpos( $content, 'class="aiv-article-outline"' ) ) {
        return $content;
    }

    $pattern = '~<h([23])\b([^>]*)>(.*?)</h\1\s*>~is';
    preg_match_all( $pattern, $content, $matches, PREG_SET_ORDER );
    if ( count( $matches ) < 3 ) {
        return $content;
    }

    $id_pattern = '~\s+id\s*=\s*(?:"([^"]+)"|\x27([^\x27]+)\x27|([^\s>]+))~i';
    preg_match_all( $id_pattern, $content, $ids, PREG_SET_ORDER );
    $reserved = array();
    foreach ( $ids as $match ) {
        $value = $match[1] ?: ( ( $match[2] ?? '' ) ?: ( $match[3] ?? '' ) );
        $reserved[ html_entity_decode( $value, ENT_QUOTES, 'UTF-8' ) ] = true;
    }

    $outline = array();
    $listed = array();
    $updated = preg_replace_callback( $pattern, function ( $match ) use ( $id_pattern, &$reserved, &$outline, &$listed ) {
        $title = trim( html_entity_decode( wp_strip_all_tags( $match[3] ), ENT_QUOTES, 'UTF-8' ) );
        if ( '' === $title || count( $outline ) >= 20 ) {
            return $match[0];
        }
        $opening = $match[2];
        if ( preg_match( $id_pattern, $opening, $existing ) ) {
            $id = $existing[1] ?: ( ( $existing[2] ?? '' ) ?: ( $existing[3] ?? '' ) );
            $id = html_entity_decode( $id, ENT_QUOTES, 'UTF-8' );
            if ( isset( $listed[ $id ] ) ) {
                return $match[0];
            }
        } else {
            $base = 'aiv-sezione-' . ( sanitize_title( $title ) ?: 'articolo' );
            $id = $base;
            for ( $suffix = 2; isset( $reserved[ $id ] ); $suffix++ ) {
                $id = $base . '-' . $suffix;
            }
            $reserved[ $id ] = true;
            $opening .= ' id="' . esc_attr( $id ) . '"';
        }
        $listed[ $id ] = true;
        $outline[] = '<li class="aiv-outline-level-' . $match[1] . '"><a href="#' . esc_attr( rawurlencode( $id ) )
            . '">' . esc_html( $title ) . '</a></li>';
        return '<h' . $match[1] . $opening . '>' . $match[3] . '</h' . $match[1] . '>';
    }, $content );

    if ( ! is_string( $updated ) || count( $outline ) < 3 ) {
        return $content;
    }
    $panel = '<details class="aiv-article-outline"><summary>In questo articolo</summary><ol>'
        . implode( '', $outline ) . '</ol></details>';
    $lead_image = '~^\s*(?:<figure\b[^>]*class="[^"]*wp-block-image[^"]*"[^>]*>.*?</figure>)~is';
    if ( preg_match( $lead_image, $updated, $image ) ) {
        $offset = strlen( $image[0] );
        return substr( $updated, 0, $offset ) . "\n" . $panel . "\n" . substr( $updated, $offset );
    }
    return $panel . "\n" . $updated;
}

function aivision_buying_context( $content ) {
    if ( ! is_main_query() || ! in_the_loop() || is_feed() ) {
        return $content;
    }

    if ( is_single( 2957 ) ) {
        if ( false !== strpos( $content, 'aiv-guide-comparison' ) ) {
            return $content;
        }
        $comparison = <<<'HTML'
<figure class="wp-block-table aiv-guide-comparison" tabindex="0">
    <table>
        <caption>Confronto rapido tra tre sedie, dalle schede dei produttori</caption>
        <thead><tr><th scope="col">Modello</th><th scope="col">Per chi</th><th scope="col">Punto forte</th><th scope="col">Da considerare</th></tr></thead>
        <tbody>
            <tr><th scope="row"><a href="https://www.corsair.com/it/it/p/gaming-chairs/cf-9010051-ww/tc100-relaxed-gaming-chair-fabric-black-black-cf-9010051-ww">Corsair TC100 Relaxed</a></th><td>Chi preferisce una seduta in tessuto</td><td>Cuscino lombare regolabile</td><td>Braccioli 2D</td></tr>
            <tr><th scope="row"><a href="https://www.corsair.com/us/en/p/gaming-chairs/cf-9010056-ww/t3-rush-fabric-gaming-chair-2023-grey-charcoal-cf-9010056-ww">Corsair T3 Rush (2023)</a></th><td>Chi vuole regolare meglio i braccioli</td><td>Braccioli 4D e rivestimento in tessuto</td><td>Seduta alta 48–58 cm</td></tr>
            <tr><th scope="row"><a href="https://www.razer.com/it-it/gaming-chairs/razer-fujin-pro">Razer Fujin Pro</a></th><td>Chi cerca una seduta in rete</td><td>Supporto lombare regolabile in altezza e profondità</td><td>Portata dichiarata fino a 136 kg</td></tr>
        </tbody>
    </table>
</figure>
HTML;
        return preg_replace( '/<h2\b/i', $comparison . "\n" . '$0', $content, 1 ) ?? $content;
    }

    if ( is_single( 2936 ) && false === strpos( $content, 'B0GZH9BJYD' ) ) {
        return $content . <<<'HTML'
<p>Il confronto riprende <a href="https://www.everyeye.it/notizie/come-gira-gta-6-ps5-ps5-pro-prestazioni-grafica-potenzialit-dualsense-912320.html">l’analisi di Davide Leoni su Everyeye</a>. La <a href="https://www.playstation.com/it-it/games/grand-theft-auto-vi/">scheda ufficiale di PlayStation</a> riporta il supporto alla vibrazione e agli effetti dei grilletti del DualSense.</p>
<section class="av-amazon-affiliate" aria-label="Edizione PlayStation 5 su Amazon">
    <p><strong>Grand Theft Auto VI per PS5 · codice download</strong></p>
    <p>La confezione contiene un codice da riscattare su PlayStation. Prezzo e disponibilità sono indicati sulla scheda del venditore.</p>
    <p>In qualità di Affiliato Amazon io ricevo un guadagno dagli acquisti idonei.</p>
    <p><a href="https://www.amazon.it/dp/B0GZH9BJYD?tag=lavocdelweb-21" rel="sponsored nofollow">Vedi l’edizione PS5 su Amazon.it</a></p>
</section>
HTML;
    }

    if ( is_page( 288 ) && false === strpos( $content, 'aiv-buying-method' ) ) {
        return $content . <<<'HTML'
<section class="aiv-buying-method">
    <h2>Come selezioniamo prodotti e offerte</h2>
    <p>Colleghiamo alla scheda di acquisto quando possiamo identificare con precisione il prodotto, la sua variante e, per i videogiochi, la piattaforma. Le guide possono basarsi su schede dei produttori, documentazione e analisi attribuite. Quando una prova è citata, indichiamo chi l’ha svolta.</p>
</section>
HTML;
    }
    return $content;
}

function aivision_editorial_navigation_styles() {
    if ( ! is_singular( 'post' ) && ! is_category( 'offerte-2' ) ) {
        return;
    }
    wp_register_style( 'aivision-editorial-navigation', false, array( 'newsup-style' ) );
    wp_enqueue_style( 'aivision-editorial-navigation' );
    wp_add_inline_style( 'aivision-editorial-navigation', <<<'CSS'
.aiv-offers-overview-wrap { width: 100%; }
.aiv-offers-overview, .aiv-article-outline {
    border: 1px solid #d8e5f5;
    border-radius: 14px;
    background: #f4f8ff;
    color: #203657;
    margin-bottom: 22px;
    padding: clamp(14px, 2vw, 22px);
}
.aiv-offers-overview {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr));
    gap: 16px 22px;
}
.aiv-offers-overview h2, .aiv-offers-archive-heading h2 { font-size: 1.2rem; margin: 0 0 9px; }
.aiv-offers-overview h2 { color: #203657; }
.aiv-offers-overview ul { list-style: none; padding: 0; margin: 0; }
.aiv-offers-overview li { display: grid; gap: 3px; padding: 7px 0; border-bottom: 1px solid #d8e5f5; }
.aiv-offers-overview time { font-size: .83rem; color: #4d6685; }
.aiv-offers-overview a, .aiv-article-outline a { color: #245698; text-decoration: underline; overflow-wrap: anywhere; }
.aiv-offers-archive-link { grid-column: 1 / -1; justify-self: start; font-weight: 700; }
.aiv-offers-archive-heading { margin: 0 0 9px; scroll-margin-top: 100px; }
.aiv-offers-archive-heading p { margin: 0; }
.aiv-article-outline { padding: 12px 16px; }
.aiv-article-outline summary { cursor: pointer; font-weight: 700; }
.aiv-article-outline ol { margin: 12px 0 0; padding-inline-start: 22px; }
.aiv-article-outline li { padding: 4px 0; }
.aiv-article-outline .aiv-outline-level-3 { margin-inline-start: 12px; }
.single main h2[id], .single main h3[id] { scroll-margin-top: 105px; }
.aiv-guide-comparison { overflow-x: auto; }
.aiv-guide-comparison table { width: 100%; min-width: 34rem; }
.aiv-guide-comparison caption { caption-side: top; color: inherit; font-weight: 700; }
CSS
    );
}
add_action( 'loop_start', 'aivision_offers_overview' );
add_filter( 'the_content', 'aivision_article_outline', 25 );
add_filter( 'the_content', 'aivision_buying_context', 26 );
add_action( 'wp_enqueue_scripts', 'aivision_editorial_navigation_styles', 31 );
