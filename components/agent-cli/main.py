#!/usr/bin/env python3
"""
Main CLI entry point for ReAct Agent
"""
import asyncio
import argparse
import sys
from pathlib import Path

from .agent import ReActAgent
from .config import AgentConfig


async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="ReAct Agent CLI - Kubernetes Operations Assistant"
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        help="Query to ask the agent"
    )
    
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash-exp",
        help="LLM model to use (default: gemini-2.0-flash-exp)"
    )
    
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum reasoning steps (default: 10)"
    )
    
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start interactive mode"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (DEBUG level)"
    )
    
    args = parser.parse_args()
    
    # Create config
    config = AgentConfig(
        model_name=args.model,
        max_steps=args.max_steps,
        log_level="DEBUG" if args.verbose else "INFO"
    )
    
    # Validate API key
    if not config.api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Create and initialize agent
    agent = ReActAgent(config)
    
    try:
        await agent.initialize()
        
        if args.interactive:
            # Interactive mode
            await interactive_mode(agent)
        elif args.query:
            # Single query mode
            result = await agent.run(args.query)
            print(f"\n{result}\n")
        else:
            # No query provided
            parser.print_help()
            sys.exit(1)
    
    finally:
        await agent.cleanup()


async def interactive_mode(agent: ReActAgent):
    """Interactive REPL mode"""
    print("\n" + "="*80)
    print("🤖 ReAct Agent - Interactive Mode")
    print("="*80)
    print("Type your queries below. Type 'exit' or 'quit' to exit.\n")
    
    while True:
        try:
            # Get user input
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!\n")
                break
            
            # Run agent
            print()
            result = await agent.run(query)
            print(f"\nAgent: {result}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!\n")
            break
        except EOFError:
            print("\n\n👋 Goodbye!\n")
            break


if __name__ == "__main__":
    asyncio.run(main())
