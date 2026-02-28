package com.idta.plc4x;

import com.idta.plc4x.model.PlcConnectionRequest;
import com.idta.plc4x.model.PlcConnectionStatus;
import com.idta.plc4x.model.PlcTag;
import com.idta.plc4x.service.PlcReader;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PlcReaderIntegrationTests {

    @Autowired
    private PlcReader plcReader;

    @Test
    void connectAndReadTagsWithSimulatedDriver() {
        PlcConnectionRequest request = new PlcConnectionRequest();
        request.setConnectionString("simulated://127.0.0.1");
        request.setName("simulated-test");

        PlcConnectionStatus connectionStatus = plcReader.connect(request);
        assertEquals(PlcConnectionStatus.ConnectionState.CONNECTED, connectionStatus.getState());
        assertNotNull(connectionStatus.getConnectionId());
        assertEquals("simulated", connectionStatus.getProtocol());

        String connectionId = connectionStatus.getConnectionId();
        try {
            Map<String, PlcTag> readResults = plcReader.readTags(connectionId, Map.of(
                    "temperature", "RANDOM/temperature:REAL",
                    "running", "RANDOM/running:BOOL"
            ));

            PlcTag temperature = readResults.get("temperature");
            PlcTag running = readResults.get("running");

            assertNotNull(temperature);
            assertNotNull(running);
            assertEquals(PlcTag.TagQuality.GOOD, temperature.getQuality());
            assertEquals(PlcTag.TagQuality.GOOD, running.getQuality());
            assertNotNull(temperature.getValue());
            assertNotNull(running.getValue());

            PlcConnectionStatus updatedStatus = plcReader.getConnectionStatus(connectionId);
            assertNotNull(updatedStatus);
            assertEquals(1L, updatedStatus.getTotalReads());
            assertEquals(0L, updatedStatus.getFailedReads());
        } finally {
            plcReader.disconnect(connectionId);
        }
    }

    @Test
    void readTagsWithoutConnectionReturnsBadQuality() {
        Map<String, PlcTag> readResults = plcReader.readTags("missing-connection", Map.of(
                "temperature", "RANDOM/temperature:REAL"
        ));

        PlcTag temperature = readResults.get("temperature");
        assertNotNull(temperature);
        assertEquals(PlcTag.TagQuality.BAD, temperature.getQuality());
        assertNull(temperature.getValue());
    }
}
