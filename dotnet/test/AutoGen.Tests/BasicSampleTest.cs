﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// BasicSampleTest.cs

using System;
using System.IO;
using System.Threading.Tasks;
using Xunit.Abstractions;

namespace AutoGen.Tests
{
    public class BasicSampleTest
    {
        private readonly ITestOutputHelper _output;

        public BasicSampleTest(ITestOutputHelper output)
        {
            _output = output;
            Console.SetOut(new ConsoleWriter(_output));
        }

        [ApiKeyFact("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")]
        public async Task AssistantAgentTestAsync()
        {
            await Example01_AssistantAgent.RunAsync();
        }

        [ApiKeyFact("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")]
        public async Task TwoAgentMathClassTestAsync()
        {
            await Example02_TwoAgent_MathChat.RunAsync();
        }

        [ApiKeyFact("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")]
        public async Task AgentFunctionCallTestAsync()
        {
            await Example03_Agent_FunctionCall.RunAsync();
        }

        [ApiKeyFact("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")]
        public async Task DynamicGroupChatGetMLNetPRTestAsync()
        {
            await Example04_Dynamic_GroupChat_Coding_Task.RunAsync();
        }

        [ApiKeyFact("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")]
        public async Task DynamicGroupChatCalculateFibonacciAsync()
        {
            await Example07_Dynamic_GroupChat_Calculate_Fibonacci.RunAsync();
            await Example07_Dynamic_GroupChat_Calculate_Fibonacci.RunWorkflowAsync();
        }

        [ApiKeyFact("OPENAI_API_KEY")]
        public async Task DalleAndGPT4VTestAsync()
        {
            await Example05_Dalle_And_GPT4V.RunAsync();
        }

        public class ConsoleWriter : StringWriter
        {
            private ITestOutputHelper output;
            public ConsoleWriter(ITestOutputHelper output)
            {
                this.output = output;
            }

            public override void WriteLine(string? m)
            {
                output.WriteLine(m);
            }
        }
    }
}
