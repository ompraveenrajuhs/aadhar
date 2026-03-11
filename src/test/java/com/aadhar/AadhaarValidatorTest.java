package com.aadhar;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AadhaarValidatorTest {

    private final AadhaarValidator validator = new AadhaarValidator();

    @Test
    void shouldValidate12DigitNumberWithChecksumRule() {
        assertTrue(validator.isValid("000000000000"));
        assertFalse(validator.isValid("000000000001"));
    }

    @Test
    void shouldRejectNonDigitOrWrongLengthInput() {
        assertFalse(validator.isValid(null));
        assertFalse(validator.isValid("1234"));
        assertFalse(validator.isValid("12345678901A"));
    }

    @Test
    void shouldMaskAllButLast4Characters() {
        assertEquals("XXXXXXXX1234", validator.mask("123412341234"));
    }

    @Test
    void shouldThrowForShortInput() {
        assertThrows(IllegalArgumentException.class, () -> validator.mask("123"));
    }

    @Test
    void shouldThrowForNullMaskInput() {
        assertThrows(IllegalArgumentException.class, () -> validator.mask(null));
    }
}
