package com.idta.plc4x.model;

import lombok.Builder;
import lombok.Data;

/**
 * Represents a PLC tag (address/variable).
 */
@Data
@Builder
public class PlcTag {

    /**
     * Tag name/identifier.
     */
    private String name;

    /**
     * PLC address in protocol-specific format.
     * Examples:
     * - Modbus: "holding-register:100:INT"
     * - S7: "%DB1.DBD0:REAL"
     * - OPC UA: "ns=2;s=Temperature"
     */
    private String address;

    /**
     * Data type of the tag.
     */
    private String dataType;

    /**
     * Current value (if read).
     */
    private Object value;

    /**
     * Quality indicator.
     */
    private TagQuality quality;

    /**
     * Timestamp of last read.
     */
    private Long timestamp;

    public enum TagQuality {
        GOOD,
        BAD,
        UNCERTAIN,
        NOT_READ
    }
}
