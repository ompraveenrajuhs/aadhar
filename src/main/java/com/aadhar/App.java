package com.aadhar;

public class App {

    public static void main(String[] args) {
        AadhaarValidator validator = new AadhaarValidator();
        String sample = args.length > 0 ? args[0] : "123412341234";

        System.out.println("Input: " + sample);
        System.out.println("Valid: " + validator.isValid(sample));
        System.out.println("Masked: " + validator.mask(sample));
    }
}

