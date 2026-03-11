package com.aadhar;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;

import static org.junit.jupiter.api.Assertions.assertTrue;

class AppTest {

    @Test
    void shouldPrintValidationAndMaskDetails() {
        PrintStream originalOut = System.out;
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        System.setOut(new PrintStream(output));

        try {
            App.main(new String[]{"000000000000"});
        } finally {
            System.setOut(originalOut);
        }

        String printed = output.toString();
        assertTrue(printed.contains("Input: 000000000000"));
        assertTrue(printed.contains("Valid: true"));
        assertTrue(printed.contains("Masked: XXXXXXXX0000"));
    }
}

