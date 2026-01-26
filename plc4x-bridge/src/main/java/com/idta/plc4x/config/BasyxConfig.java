package com.idta.plc4x.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * BaSyx AAS Server configuration.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "basyx")
public class BasyxConfig {

    /**
     * AAS Server configuration.
     */
    private AasServerConfig aasServer = new AasServerConfig();

    /**
     * Submodel endpoint template.
     */
    private String submodelEndpoint = "/shells/{shellId}/submodels/{submodelId}/submodel-elements";

    @Data
    public static class AasServerConfig {
        /**
         * Base URL of the BaSyx AAS Server.
         */
        private String url = "http://basyx-aas-server:4001";
    }

    /**
     * Create WebClient for BaSyx API calls.
     */
    @Bean
    public WebClient basyxWebClient() {
        return WebClient.builder()
                .baseUrl(aasServer.getUrl())
                .defaultHeader("Content-Type", "application/json")
                .build();
    }
}
